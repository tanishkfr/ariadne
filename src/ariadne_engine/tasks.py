"""Universal task entry: interpretation, workflow selection, and task planning (Ariadne 2.3A).

``$ariadne`` must accept an everyday engineering request ("fix the failing export
in this React app") without forcing it through a creative-production project.
This module is the intelligence for that entry point. It sits *above* the
existing engine and owns exactly three decisions:

1. **What was asked.** An interpretation frame — action, object, artifact role,
   unresolved slots — built from the request, the declared vocabulary, and the
   actual state of the project on disk. Token evidence is recorded evidence, not
   a lookup table; when the evidence conflicts or runs out the frame stays
   unresolved and the plan asks one question instead of guessing.
2. **Which workflow.** ``project`` keeps the full creative workflow and its
   human direction gate (five modes, Design Intelligence, G1..G5 — unchanged,
   owned by ``ROUTER.md`` and the creative plan). ``task`` is the lightweight
   workflow for one bounded engineering outcome. ``resume`` continues a run that
   already exists. ``unresolved`` asks before committing.
3. **How the task is prepared.** The plan reuses the existing engines: the task
   characterisation is :func:`ariadne_engine.routing.characterize`, the path is
   :func:`ariadne_engine.orchestration.path_plan`, and the skills come from
   :mod:`ariadne_engine.skills`. Nothing here replaces them.

What this module deliberately does not do: it does not route a *stage* to a
provider or worker role (:func:`routing.route` remains the single owner), it does
not verify anything (``proof.py`` remains the verification authority), it does
not grant approvals, and it never prepares a packet itself — the runtime and the
transport do that, from this plan.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Mapping, Sequence

from . import contracts, orchestration, routing, skills
from .contracts import ContractError

PLAN_POLICY = "task-entry-plan-1"

INTENT_FAMILIES = (
    "new-project",
    "continue-project",
    "feature",
    "bug",
    "refactor",
    "performance",
    "audit",
    "ui-redesign",
    "research",
    "verification",
)
"""The intent families ``$ariadne`` understands.

The five creative *modes* are not replaced: they belong to the project
workflow, and this vocabulary only selects between that workflow and the
lightweight task workflow.
"""

PROJECT_FAMILIES = ("new-project",)
READ_ONLY_FAMILIES = ("research", "verification")
AUDIT_FAMILIES = ("audit",)

WORKFLOW_PROJECT = "project"
WORKFLOW_TASK = "task"
WORKFLOW_RESUME = "resume"
WORKFLOW_UNRESOLVED = "unresolved"
WORKFLOW_FAMILIES = (WORKFLOW_PROJECT, WORKFLOW_TASK, WORKFLOW_RESUME, WORKFLOW_UNRESOLVED)

STATUS_READY = "ready"
STATUS_NEEDS_HUMAN = "needs-human"
STATUS_BLOCKED = "blocked"
PLAN_STATUSES = (STATUS_READY, STATUS_NEEDS_HUMAN, STATUS_BLOCKED)

ACTION_VOCABULARY = ("CREATE", "TRANSFORM", "ANALYZE", "RESTART", "EXTEND")
"""The ROUTER.md frame actions, reused rather than reinvented."""

ACTION_EVIDENCE: dict[str, tuple[str, ...]] = {
    "CREATE": ("build", "create", "make", "scaffold", "generate a", "design a", "write a", "start a", "new "),
    "TRANSFORM": ("redesign", "restyle", "rework", "revamp", "convert", "port", "optimise", "optimize",
                  "refactor", "clean up", "simplify", "speed up"),
    "ANALYZE": ("review", "audit", "analyse", "analyze", "critique", "inspect", "explain", "understand",
                "investigate", "diagnose", "profile", "benchmark", "why does", "why is", "how does",
                "how do", "what does", "check whether", "verify"),
    "RESTART": ("start over", "scrap this", "abandon", "rethink", "new direction", "throw away"),
    "EXTEND": ("fix", "bug", "continue", "resume", "improve", "extend", "add", "implement", "support",
               "handle", "upgrade"),
}
"""Declared action evidence. Calibration samples, not a lookup table (R-ACT-1).

The interpretation prefers the stated action, resolves unknowns explicitly, and
never lets an artifact or a noun choose the workflow by itself.
"""

CREATIVE_OBJECT_TOKENS = (
    "website", "web site", "site", "portfolio", "landing page", "game", "installation",
    "brand", "identity", "poster", "article", "essay", "book", "campaign", "social post",
    "thread", "newsletter", "ui design", "visual identity",
)
TECHNICAL_OBJECT_TOKENS = (
    "function", "module", "api", "endpoint", "bug", "code", "codebase", "repository", "repo",
    "script", "test", "tests", "build", "backend", "frontend", "database", "query", "migration",
    "component", "class", "method", "library", "package", "cli", "service", "server", "react app",
    "app", "typescript", "python", "javascript", "compile", "stack trace", "log", "configuration",
)

FAMILY_EVIDENCE: dict[str, tuple[str, ...]] = {
    "bug": ("bug", "broken", "breaks", "crash", "crashes", "error", "exception", "fails", "failing",
            "failure", "regression", "doesn't work", "does not work", "not working", "stack trace",
            "incorrect", "wrong output", "freezes", "hangs"),
    "feature": ("add ", "implement", "support for", "new feature", "build a", "provide a", "expose a",
                "enable", "introduce"),
    "refactor": ("refactor", "restructure", "reorganise", "reorganize", "clean up", "simplify",
                 "extract", "deduplicate", "technical debt", "rename across"),
    "performance": ("slow", "performance", "optimise", "optimize", "latency", "memory usage",
                    "bundle size", "speed up", "faster", "takes too long", "bottleneck", "profile"),
    "audit": ("audit", "architecture review", "code review", "security review", "technical review",
              "assess the code", "evaluate the code", "code quality"),
    "research": ("explain", "how does", "how do", "what does", "understand", "walk me through",
                 "read through", "figure out how", "investigate how", "summarise", "summarize"),
    "verification": ("verify", "check whether", "did it actually", "does it actually", "confirm that",
                     "is it actually", "prove that", "validate that"),
    "new-project": ("new website", "new site", "from scratch", "brand new project", "start a project",
                    "new project"),
    "ui-redesign": ("redesign", "restyle", "revamp", "refresh the visual", "visual refresh",
                    "update the design", "change the layout", "rework the interface", "typography",
                    "styling", "spacing", "responsive", "design system", "look and feel"),
    "continue-project": ("continue", "resume", "carry on", "pick up where", "keep working on"),
}

DESIGN_EVIDENCE = ("ui", "ux", "visual", "design", "interface", "layout", "typography", "styling",
                   "responsive", "colour", "color", "animation", "spacing")
"""Signals that a task carries a design obligation, whatever its family."""

RENDERED_SURFACE_EVIDENCE = (
    "modal", "dialog", "popup", "overlay", "dropdown", "menu", "toolbar", "navbar", "sidebar",
    "panel", "page", "screen", "view", "form", "button", "widget", "dashboard", "component",
    "editor", "canvas", "carousel", "gallery", "landing", "hero", "banner",
    "css", "html", "jsx", "tsx", "frontend", "web app", "website",
)
"""Request signals that name a surface a browser actually paints.

A rendered defect ("the modal is clipped") names no design vocabulary, so the
design-token list alone would miss it. These tokens are the second detector: when
one is present in a writing task, an unrendered implementation cannot be called
visually verified.
"""

RENDERED_FILE_SUFFIXES = (".html", ".css", ".scss", ".sass", ".less", ".jsx", ".tsx", ".vue", ".svelte", ".astro")

RENDERED_MODES = ("auto", "required", "off")

INTERACTION_EVIDENCE = ("interaction", "click", "hover", "drag", "animation", "animate", "transition",
                        "toggle", "carousel", "accordion", "open", "close", "keyboard", "focus")

WRITE_EVIDENCE = ("fix", "implement", "add ", "build", "create", "change", "update", "repair",
                  "refactor", "rename", "migrate", "replace", "remove", "optimise", "optimize")
DEPLOY_EVIDENCE = ("deploy", "ship", "publish", "release to production", "push to production")
"""Requests that leave the machine keep their existing gates: G4 and G5."""

DESIGN_LOCK_PATTERN = re.compile(r"(?im)^\*\*Status:\*\*\s*locked at G1")
GATE_RECORD_PATTERN = re.compile(r"(?im)^\|\s*\*\*Last gate passed\*\*\s*\|\s*`?(G[1-5])")


class TaskPlanError(ContractError):
    """A plan request that cannot be honoured. Nothing was changed."""


def inspect_project(project: Path) -> dict:
    """Cheap, deterministic evidence about the project directory.

    This is discovery, not judgement: it records what is present so the
    interpretation can use real state instead of assumptions. It reads at most a
    few small files and never walks the tree.
    """
    project = Path(project)
    evidence: dict = {
        "path": str(project),
        "exists": project.is_dir(),
        "entries": [],
        "source_markers": [],
        "creative_documents": [],
        "design_locked": False,
        "gate_recorded": "",
        "git_repository": (project / ".git").exists(),
        "empty": False,
        "has_source_tree": False,
    }
    if not project.is_dir():
        return evidence
    try:
        entries = sorted(item.name for item in project.iterdir())
    except OSError:
        return evidence
    evidence["entries"] = entries
    evidence["empty"] = not [
        name for name in entries if name not in (".git", ".gitignore")
    ]
    markers = (
        "package.json", "pyproject.toml", "Cargo.toml", "go.mod", "requirements.txt",
        "composer.json", "Gemfile", "build.gradle", "pom.xml", "CMakeLists.txt", "Makefile",
    )
    evidence["source_markers"] = [name for name in markers if name in entries]
    source_dirs = ("src", "lib", "app", "apps", "packages", "tests", "test")
    evidence["source_directories"] = [name for name in source_dirs if (project / name).is_dir()]
    evidence["has_source_tree"] = bool(evidence["source_markers"] or evidence["source_directories"])
    creative = [name for name in ("PROJECT.md", "DESIGN.md", "HANDOFF.md", "QA.md") if name in entries]
    evidence["creative_documents"] = creative
    design = project / "DESIGN.md"
    if design.is_file():
        try:
            evidence["design_locked"] = bool(DESIGN_LOCK_PATTERN.search(design.read_text(encoding="utf-8")))
        except OSError:
            evidence["design_locked"] = False
    agents = project / "AGENTS.md"
    if agents.is_file():
        try:
            match = GATE_RECORD_PATTERN.search(agents.read_text(encoding="utf-8"))
            evidence["gate_recorded"] = match.group(1) if match else ""
        except OSError:
            evidence["gate_recorded"] = ""
    return evidence


def _tokens(text: str) -> str:
    return " " + str(text or "").lower() + " "


def _matches(evidence_tokens: Sequence[str], text: str) -> list[str]:
    """Declared tokens present in the text, matched on word boundaries.

    Word boundaries matter for honesty here: a plain substring search matches
    "ui" inside "build" and "api" inside "rapid", which would silently change
    the interpretation. A token must be a word in the request.
    """
    lowered = str(text or "").lower()
    hits = []
    for token in evidence_tokens:
        needle = str(token).strip()
        if not needle:
            continue
        if re.search(r"\b" + re.escape(needle) + r"\b", lowered):
            hits.append(str(token))
    return hits


OVERLAP_RESOLUTIONS: dict[frozenset, str] = {
    frozenset(("bug", "performance")): "performance",
    frozenset(("refactor", "performance")): "refactor",
    frozenset(("audit", "refactor")): "audit",
}
"""Realistic overlaps and the family that owns them, each with a stated reason.

Two families that overlap without a resolution rule leave the plan unresolved,
because guessing between materially different workflows is exactly the failure
the frame exists to prevent.
"""

OVERLAP_REASONS = {
    frozenset(("bug", "performance")): "the request frames the defect as a measurable behaviour",
    frozenset(("refactor", "performance")): "the request frames the change as structural, not a measured target",
    frozenset(("audit", "refactor")): "the request asks for judgement about existing structure",
}


def interpret(
    request: str,
    *,
    declared_intent: str = "",
    declared_action: str = "",
    declared_object: str = "",
    project_evidence: Mapping | None = None,
) -> dict:
    """Build the interpretation frame for one request.

    Returns a frame record with the action, object, family, evidence for each
    choice, confidence, and the exact unresolved slots. A caller that has already
    interpreted the request (the assistant reading the human's words) passes the
    slots it resolved; the frame records them as user-declared, which is an
    authority this module honours rather than second-guesses.
    """
    evidence = dict(project_evidence or {})
    text = str(request or "")
    action = str(declared_action or "").upper()
    action_source = "user-declared" if action else ""
    if action and action not in ACTION_VOCABULARY:
        raise TaskPlanError(f"declared action is not part of the frame vocabulary: {declared_action!r}")
    action_matches: dict[str, list[str]] = {}
    for name, tokens in ACTION_EVIDENCE.items():
        hits = _matches(tokens, text)
        if hits:
            action_matches[name] = hits
    if not action:
        if len(action_matches) == 1:
            action = next(iter(action_matches))
            action_source = "rule-derived"
        elif len(action_matches) > 1:
            ordered = [name for name in ACTION_VOCABULARY if name in action_matches]
            action = ordered[0]
            action_source = "rule-derived (priority order; conflicting evidence recorded)"
        else:
            action, action_source = "", ""

    creative_hits = _matches(CREATIVE_OBJECT_TOKENS, text)
    technical_hits = _matches(TECHNICAL_OBJECT_TOKENS, text)
    declared_object_value = str(declared_object or "").strip()
    if declared_object_value:
        object_value = declared_object_value
        object_source = "user-declared"
        declared_creative = _matches(CREATIVE_OBJECT_TOKENS, declared_object_value)
        declared_technical = _matches(TECHNICAL_OBJECT_TOKENS, declared_object_value)
        if declared_creative and not declared_technical:
            object_kind = "creative"
        elif declared_technical and not declared_creative:
            object_kind = "technical"
        else:
            object_kind = "declared"
    elif creative_hits and not technical_hits:
        object_value, object_source, object_kind = creative_hits[0], "rule-derived", "creative"
    elif technical_hits and not creative_hits:
        object_value, object_source, object_kind = technical_hits[0], "rule-derived", "technical"
    elif creative_hits and technical_hits:
        object_value, object_source, object_kind = "mixed", "rule-derived", "mixed"
    elif evidence.get("has_source_tree") or evidence.get("creative_documents"):
        # The request names no object, but the project itself is visible: an
        # existing source tree or a project that already carries Ariadne
        # documents is the thing the work is about (Ariadne 2.3B attaches a
        # bounded task to exactly that history). Only a genuinely empty or
        # unknown directory leaves the object unresolved.
        object_value, object_source, object_kind = "the existing project", "runtime-observed", "technical"
    else:
        object_value, object_source, object_kind = "UNRESOLVED", "not-observed", "unresolved"

    family_matches: dict[str, list[str]] = {}
    for family_name, tokens in FAMILY_EVIDENCE.items():
        hits = _matches(tokens, text)
        if hits:
            family_matches[family_name] = hits
    candidates = sorted(family_matches)
    conflicted = False
    resolution_note = ""
    if len(candidates) > 1:
        pair = frozenset(candidates)
        resolved = OVERLAP_RESOLUTIONS.get(pair)
        if resolved:
            resolution_note = OVERLAP_REASONS[pair]
            candidates = [resolved]
        else:
            conflicted = True
    family = ""
    family_source = ""
    if declared_intent:
        if declared_intent not in INTENT_FAMILIES:
            raise TaskPlanError(
                f"declared intent is not a known family: {declared_intent!r}; "
                f"choose one of {', '.join(INTENT_FAMILIES)}"
            )
        family, family_source = declared_intent, "user-declared"
    elif len(candidates) == 1:
        family, family_source = candidates[0], "rule-derived"
    elif conflicted:
        family, family_source = "", "conflicting-evidence"

    if not family and not declared_intent and not conflicted:
        object_from_request = object_source in ("rule-derived", "user-declared")
        if action in ("CREATE", "TRANSFORM") and object_kind == "creative" and object_from_request:
            family, family_source = "new-project", "rule-derived"
        elif action in ("CREATE", "EXTEND", "TRANSFORM") and object_kind == "technical" and object_from_request:
            family, family_source = "feature", "rule-derived"
        elif action == "ANALYZE" and object_kind == "technical" and object_from_request:
            family, family_source = "audit", "rule-derived"

    if family == "new-project":
        explicit_new = _matches(FAMILY_EVIDENCE["new-project"], text)
        if explicit_new:
            resolution_note = resolution_note or (
                "the request itself declares a new project, so existing files do not reclassify it"
            )
        elif evidence.get("has_source_tree") and not evidence.get("creative_documents"):
            family, family_source = "feature", "runtime-observed (existing source tree)"
            resolution_note = "the project already contains source; this extends it rather than starting over"
        elif evidence.get("creative_documents"):
            family, family_source = "continue-project", "runtime-observed (project documents present)"
            resolution_note = "the project already carries Ariadne documents; continue it instead"

    write_hits = _matches(WRITE_EVIDENCE, text)
    deploy_hits = _matches(DEPLOY_EVIDENCE, text)
    read_only = family in READ_ONLY_FAMILIES or (family == "audit" and not write_hits)
    design_obligation = family == "ui-redesign" or (
        family in ("new-project",) and object_kind == "creative"
    )
    unresolved: list[dict] = []
    if not family:
        unresolved.append({
            "slot": "family",
            "question": (
                "What outcome do you want: fix a defect, add a capability, improve speed, "
                "refactor, audit the code, understand it, or start a new project?"
            ),
            "why": "the request does not resolve to one intent family",
        })
    if object_kind == "unresolved":
        unresolved.append({
            "slot": "object",
            "question": "What is the thing this work is about?",
            "why": "no object is named or visible in the project",
        })
    if object_kind == "mixed" and not family:
        unresolved.append({
            "slot": "object",
            "question": "Is this a technical change to the project, or design work on it?",
            "why": "the request names both technical and visual objects",
        })
    confidence = "HIGH"
    if unresolved:
        confidence = "LOW"
    elif family_source.startswith("rule-derived (priority") or resolution_note:
        confidence = "MEDIUM"
    return {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "action": action,
        "action_source": action_source,
        "object": object_value,
        "object_source": object_source,
        "object_kind": object_kind,
        "family": family,
        "family_source": family_source,
        "read_only": bool(read_only),
        "design_obligation": bool(design_obligation),
        "write_requested": bool(write_hits) and not read_only,
        "deploy_requested": bool(deploy_hits),
        "candidates": candidates,
        "evidence": {
            "actions": {name: hits for name, hits in sorted(action_matches.items())},
            "families": {name: hits for name, hits in sorted(family_matches.items())},
            "creative_object": creative_hits,
            "technical_object": technical_hits,
            "write_intent": write_hits,
            "deploy_intent": deploy_hits,
            "resolution": resolution_note,
        },
        "confidence": confidence,
        "unresolved": unresolved,
    }


def _workflow_for(
    frame: Mapping,
    *,
    project: Path,
    project_evidence: Mapping,
    run_roots: Sequence[str],
) -> dict:
    """Choose the workflow family from the interpreted frame and real state."""
    family = str(frame.get("family", ""))
    runs = [str(item) for item in run_roots if str(item)]
    if not family:
        return {"family": WORKFLOW_UNRESOLVED, "reason": "the interpretation is unresolved", "resume": {}}
    if family == "continue-project":
        if runs:
            return {
                "family": WORKFLOW_RESUME,
                "reason": "a run already records this project; resume it instead of creating a second history",
                "resume": {"runs": runs},
            }
        return {
            "family": WORKFLOW_UNRESOLVED,
            "reason": "the request continues a project, but no run records this project",
            "resume": {},
        }
    if family in PROJECT_FAMILIES and runs:
        return {
            "family": WORKFLOW_UNRESOLVED,
            "reason": (
                "a run already records this project, so a request to start a new project is either "
                "a continuation or a deliberately separate project"
            ),
            "resume": {"runs": runs},
        }
    if family in PROJECT_FAMILIES:
        return {
            "family": WORKFLOW_PROJECT,
            "reason": (
                "a new creative project keeps the full workflow: Design Intelligence, "
                "the five modes, and the human direction gate"
            ),
            "resume": {},
        }
    if family == "audit" and str(frame.get("object_kind", "")) == "creative":
        return {
            "family": WORKFLOW_PROJECT,
            "reason": "judging a creative artifact is the audit-review mode of the existing workflow",
            "resume": {},
        }
    if family == "ui-redesign":
        design_locked = bool(project_evidence.get("design_locked")) or str(
            project_evidence.get("gate_recorded", "")
        ).startswith("G1")
        if not design_locked:
            return {
                "family": WORKFLOW_PROJECT,
                "reason": (
                    "no approved design direction exists for this project; a redesign would set one, "
                    "so it belongs to the full workflow with its human G1 gate"
                ),
                "resume": {},
            }
        return {
            "family": WORKFLOW_TASK,
            "reason": (
                "an approved direction exists; redesign work refines it under the existing G1 decision "
                "and does not reopen the direction gate"
            ),
            "resume": {},
        }
    result = {
        "family": WORKFLOW_TASK,
        "reason": f"one bounded engineering outcome ({family}) does not need the creative project workflow",
        "resume": {},
    }
    if runs:
        # Honest before preparation: a second history for a recorded project is
        # refused by the runtime, so the plan says so now rather than after.
        result["existing_runs"] = runs
        result["reason"] += (
            "; a run already records this project, so preparation will ask you to resume it"
        )
    return result


def _questions_for(frame: Mapping, *, scope: Sequence[str], validation: Sequence[str], workflow: Mapping) -> list[dict]:
    questions = [dict(item) for item in frame.get("unresolved") or ()]
    if workflow.get("family") == WORKFLOW_TASK and not frame.get("read_only"):
        if not scope:
            questions.append({
                "slot": "scope",
                "question": "Which files, directories, or modules may I change? A bounded scope is part of the task contract.",
                "why": "the worker contract refuses an unbounded or guessed scope",
            })
        if not validation:
            questions.append({
                "slot": "validation",
                "question": "Which command should prove the change works? (for example: npm test, pytest, cargo test)",
                "why": "a task packet needs at least one required validation command the engine can rerun",
            })
    return questions


def _protected_scope(scope: Sequence[str], frame: Mapping) -> list[dict]:
    protected = []
    for raw in scope:
        text = str(raw)
        lowered = text.replace("\\", "/").lower()
        for segment in routing.SENSITIVE_SEGMENTS:
            if segment in lowered:
                protected.append({
                    "path": text,
                    "reason": f"the scope names the sensitive subsystem {segment!r}",
                    "gate": "human-authorization",
                })
                break
    if frame.get("deploy_requested"):
        protected.append({
            "path": "publish/deploy",
            "reason": "the request asks for work that leaves the machine",
            "gate": "G4",
        })
    return protected


def _detected_validation(project: Path, evidence: Mapping) -> list[str]:
    """Validation commands suggested from real project files, never invented.

    A suggestion is a recommendation for the human or the assistant to accept;
    it is never the validation authority.
    """
    detected: list[str] = []
    package = Path(project) / "package.json"
    if package.is_file():
        try:
            value = json.loads(package.read_text(encoding="utf-8"))
            scripts = value.get("scripts") or {}
            for name in ("test", "build", "lint", "typecheck", "check"):
                if name in scripts:
                    detected.append(f"npm run {name}")
        except (OSError, ValueError):
            pass
    if "pyproject.toml" in (evidence.get("source_markers") or []) or (Path(project) / "tests").is_dir():
        detected.append("python -m pytest")
    if "Cargo.toml" in (evidence.get("source_markers") or []):
        detected.append("cargo test")
    if "go.mod" in (evidence.get("source_markers") or []):
        detected.append("go test ./...")
    if "Makefile" in (evidence.get("source_markers") or []):
        detected.append("make test")
    return detected


def _rendered_acceptance(
    *,
    request: str,
    scope: Sequence[str],
    frame: Mapping,
    workflow_family: str,
    design_obligation: bool,
    declared: str,
    capture_capability: Mapping | None,
    render_target: Mapping | None = None,
) -> dict:
    """Whether this task must carry rendered (browser) acceptance evidence.

    Detection is deterministic and recorded: the request's own words, the declared
    scope's file kinds, and the design obligation, each with its evidence. The
    capture capability is never assumed: it is whatever the caller probed, and an
    unavailable capability is reported as a gap here so a later "visually verified"
    claim has nowhere to hide.
    """
    mode = str(declared or "auto").strip().lower() or "auto"
    if mode not in RENDERED_MODES:
        raise TaskPlanError(f"unknown rendered-acceptance mode: {mode!r}")
    reasons: list[str] = []
    if mode == "off":
        return {
            "mode": mode,
            "required": False,
            "reasons": ["rendered acceptance was explicitly turned off for this task"],
            "interaction": False,
            "capture_capability": dict(capture_capability or {"status": "UNKNOWN", "detail": "not probed"}),
            "obligation": "none",
        }
    if workflow_family != WORKFLOW_TASK or bool(frame.get("read_only")):
        return {
            "mode": mode,
            "required": False,
            "reasons": [
                "rendered acceptance applies to bounded writing tasks; this task is "
                + ("read-only" if frame.get("read_only") else f"a {workflow_family or 'non-task'} workflow")
            ],
            "interaction": False,
            "capture_capability": dict(capture_capability or {"status": "UNKNOWN", "detail": "not probed"}),
            "obligation": "none",
        }
    surface_hits = _matches(RENDERED_SURFACE_EVIDENCE, request)
    scope_hits = [
        str(item) for item in scope
        if str(item).lower().endswith(RENDERED_FILE_SUFFIXES)
    ]
    if design_obligation:
        reasons.append("the task carries a design obligation")
    if surface_hits:
        reasons.append("the request names a rendered surface: " + ", ".join(surface_hits[:5]))
    if scope_hits:
        reasons.append("the declared scope includes rendered files: " + ", ".join(scope_hits[:4]))
    if mode == "required":
        required = True
        reasons.append("rendered acceptance was explicitly required")
    else:
        required = bool(reasons)
    interaction = required and (
        bool(_matches(INTERACTION_EVIDENCE, request)) or design_obligation
    )
    capability = dict(capture_capability or {"status": "UNKNOWN", "detail": "not probed"})
    result = {
        "mode": mode,
        "required": required,
        "reasons": reasons or ["no rendered surface is named by the request or the scope"],
        "interaction": bool(interaction),
        "capture_capability": capability,
        "obligation": "browser-render" if required else "none",
    }
    if required:
        target = dict(render_target or {})
        actions = [
            dict(item) if isinstance(item, Mapping) else {"kind": "click", "selector": str(item)}
            for item in target.get("actions") or ()
        ]
        result["target"] = {
            "route": str(target.get("route", "") or "/"),
            "serve_dir": str(target.get("serve_dir", "")),
            "actions": actions,
            "expect": [str(item) for item in target.get("expect") or ()],
        }
        if actions and not result["interaction"]:
            # The operator declared an interaction to capture; a plan that then
            # photographs only the default state would file the interaction's name
            # on the default's picture.
            result["interaction"] = True
            result["reasons"] = list(result["reasons"]) + [
                "an interaction was declared for capture: "
                + ", ".join(str(item.get("selector") or item.get("kind")) for item in actions[:3])
            ]
    return result


def plan(
    *,
    request: str,
    project: Path,
    project_evidence: Mapping | None = None,
    run_roots: Sequence[str] = (),
    declared_intent: str = "",
    declared_action: str = "",
    declared_object: str = "",
    scope: Sequence[str] = (),
    validation: Sequence[str] = (),
    dependencies: Sequence[str] = (),
    declared_capabilities: Mapping | Sequence | None = None,
    explicit_skills: Sequence[str] = (),
    declared_rendered: str = "",
    capture_capability: Mapping | None = None,
    render_target: Mapping | None = None,
    approved_external: Sequence[str] = (),
    skill_registry: Mapping | None = None,
    task_id: str = "",
    run_id: str = "",
) -> dict:
    """Build the universal-entry plan for one request.

    The plan never writes anything. It is a record a human or an assistant can
    inspect before ``task-start`` prepares — or refuses — a worker packet.
    """
    project = Path(project)
    evidence = dict(project_evidence or inspect_project(project))
    frame = interpret(
        request,
        declared_intent=declared_intent,
        declared_action=declared_action,
        declared_object=declared_object,
        project_evidence=evidence,
    )
    workflow = _workflow_for(
        frame, project=project, project_evidence=evidence, run_roots=run_roots,
    )

    prior_failures = 0
    characterisation: dict = {}
    if workflow["family"] == WORKFLOW_TASK:
        stage = "S4B"
        boundary = "read-only-investigation" if frame["read_only"] else "task-implementation"
        characterisation = routing.characterize(
            {},
            project=project,
            stage=stage,
            task_id=task_id,
            request=request,
            dependencies=tuple(str(item) for item in dependencies),
            boundary=boundary,
        )
        problems = routing.characterisation_problems(characterisation)
        if problems:
            raise TaskPlanError("the task characterisation is malformed: " + "; ".join(problems))
        prior_failures = len(characterisation.get("prior_failures") or [])

    difficulty = str((characterisation.get("difficulty") or {}).get("value", "UNKNOWN"))
    stakes = str((characterisation.get("stakes") or {}).get("value", "UNKNOWN"))
    required_capabilities = [
        str(item.get("id")) for item in (characterisation.get("required_capabilities") or ())
    ]
    design_obligation = (
        frame["family"] == "ui-redesign"
        or (frame["family"] == "new-project" and frame["object_kind"] == "creative")
        or bool(_matches(DESIGN_EVIDENCE, request))
    ) and workflow["family"] != WORKFLOW_PROJECT
    design_locked = bool(evidence.get("design_locked")) or str(
        evidence.get("gate_recorded", "")
    ).startswith("G1")
    execution_path: dict = {}
    if workflow["family"] == WORKFLOW_TASK:
        review_required = (
            stakes == "HIGH"
            or difficulty == "HIGH"
            or frame["family"] in AUDIT_FAMILIES
            or design_obligation
        )
        execution_path = orchestration.path_plan(
            stakes=stakes,
            difficulty=difficulty,
            design_required=design_obligation,
            required_capabilities=required_capabilities,
            prior_failures=prior_failures,
            verification_required=True,
            review_required=review_required,
        )
        path_problems = orchestration.require_verification_retained(execution_path)
        if path_problems:
            raise TaskPlanError("the execution path lost required verification: " + "; ".join(path_problems))

    write_authorization = "none" if frame["read_only"] else "bounded"
    host = skills.host_capabilities(declared_capabilities)
    selection = skills.select_skills(
        intent_family=str(frame["family"] or ""),
        workflow=WORKFLOW_PROJECT if workflow["family"] == WORKFLOW_PROJECT else WORKFLOW_TASK,
        characterisation=characterisation,
        plan={**execution_path, "write_authorization": write_authorization},
        host=host,
        explicit=explicit_skills,
        approved_external=tuple(str(item) for item in approved_external),
        registry=skill_registry,
        run_id=run_id,
        task_id=task_id,
    )
    selection_problems = skills.selection_problems(selection)
    if selection_problems:
        raise TaskPlanError("the skill selection is malformed: " + "; ".join(selection_problems))

    protected = _protected_scope(scope, frame)
    rendered_acceptance = _rendered_acceptance(
        request=request,
        scope=scope,
        frame=frame,
        workflow_family=str(workflow["family"]),
        design_obligation=design_obligation,
        declared=declared_rendered,
        capture_capability=capture_capability,
        render_target=render_target,
    )
    questions = _questions_for(
        frame, scope=scope, validation=validation, workflow=workflow,
    )
    gaps = [dict(item) for item in selection.get("gaps") or []]
    if rendered_acceptance["required"] and str(
        (rendered_acceptance.get("capture_capability") or {}).get("status", "")
    ) == "UNAVAILABLE":
        gaps.append({
            "capability": "capture",
            "skill": "visual-qa",
            "reason": "this task requires browser-rendered acceptance evidence, but the capture "
                      "capability is unavailable: "
                      + str((rendered_acceptance.get("capture_capability") or {}).get("detail", "no detail")),
        })
    if selection.get("status") == "refused":
        gaps.append({
            "capability": "skill-selection",
            "skill": "",
            "reason": "the skill selection refused contradictory instructions: "
                      + "; ".join(str(item.get("reason", "")) for item in selection.get("conflicts") or ()),
        })

    status = STATUS_READY
    if workflow["family"] == WORKFLOW_UNRESOLVED or questions:
        status = STATUS_NEEDS_HUMAN
    if protected:
        status = STATUS_BLOCKED
    if selection.get("status") == "refused":
        status = STATUS_BLOCKED

    gates_ahead: list[str] = []
    if workflow["family"] == WORKFLOW_PROJECT or (design_obligation and not design_locked):
        gates_ahead.append("G1")
    if dependencies:
        gates_ahead.append("G2")
    if not frame["read_only"] and workflow["family"] == WORKFLOW_TASK:
        gates_ahead.append("G3")
    if frame.get("deploy_requested"):
        gates_ahead.append("G4")

    next_action = _next_action(
        workflow=workflow,
        frame=frame,
        status=status,
        questions=questions,
        protected=protected,
    )
    record = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "plan_id": contracts.new_record_id("tskp"),
        "run_id": str(run_id),
        "task_id": str(task_id),
        "project": str(project),
        "request": str(request),
        "policy": PLAN_POLICY,
        "frame": frame,
        "workflow": workflow,
        "characterisation": characterisation,
        "path": execution_path,
        "skills": selection,
        "capabilities": {
            "host": {str(name): str(value.get("status")) for name, value in sorted(
                dict(host.get("values") or {}).items())},
            "host_source": str(host.get("source", "")),
            "required": [str(item) for item in selection.get("required_capabilities") or ()],
            "gaps": gaps,
        },
        "scope": {
            "declared": [str(item) for item in scope],
            "unresolved": not scope and workflow["family"] == WORKFLOW_TASK and not frame["read_only"],
            "protected": protected,
        },
        "validation": {
            "declared": [str(item) for item in validation],
            "detected": _detected_validation(project, evidence),
            "requirement": "at least one required command before a worker packet is prepared",
        },
        "dependencies": [str(item) for item in dependencies],
        "rendered_acceptance": rendered_acceptance,
        "write_authorization": write_authorization,
        "approvals": {
            "gates_ahead": gates_ahead,
            "note": "a plan names the gates ahead; it can never grant one",
        },
        "project_evidence": {
            "exists": bool(evidence.get("exists")),
            "has_source_tree": bool(evidence.get("has_source_tree")),
            "creative_documents": list(evidence.get("creative_documents") or ()),
            "design_locked": bool(evidence.get("design_locked")),
            "gate_recorded": str(evidence.get("gate_recorded", "")),
            "empty": bool(evidence.get("empty")),
        },
        "questions": questions,
        "status": status,
        "next": next_action,
        "policy_version": contracts.POLICY_VERSION,
        "recorded_at": contracts.utc_now(),
    }
    problems = plan_problems(record)
    if problems:
        raise TaskPlanError("the task plan is malformed: " + "; ".join(problems))
    return record


def _next_action(*, workflow: Mapping, frame: Mapping, status: str, questions: Sequence[Mapping], protected: Sequence[Mapping]) -> str:
    family = str(workflow.get("family", ""))
    if status == STATUS_BLOCKED and protected:
        first = protected[0]
        if str(first.get("gate")) == "G4":
            return "Stop: work that leaves the machine needs the human G4 ship decision before preparation."
        return (
            f"Stop: {first.get('reason')} ({first.get('path')}). This needs explicit human "
            "authorization before any preparation."
        )
    if family == WORKFLOW_UNRESOLVED:
        return "Ask the question and wait: " + str(questions[0].get("question", "")) if questions else (
            "Ask the human what outcome they want before preparing anything."
        )
    if family == WORKFLOW_PROJECT:
        return (
            "Start the full project workflow: `ariadne.py start --project <project> --request <request>`. "
            "The creative plan selects its own skills; the direction gate stays human."
        )
    if family == WORKFLOW_RESUME:
        return "Resume the recorded run: `ariadne.py status --project <project>` and continue from its next action."
    if questions:
        return "Resolve the open task-contract questions, then run `ariadne.py task-start`."
    if frame.get("read_only"):
        return (
            "Perform the read-only investigation in this session; no worker packet and no write "
            "authorization are needed. Ariadne verification stays available for claims."
        )
    return "Prepare the task: `ariadne.py task-start --project <project> --request <request>`."


CONTRACT_HEADING = "## Worker execution contract"


def _single_line(value: str) -> str:
    """Collapse a value to one line: the contract parser reads fields by line."""
    return " ".join(str(value or "").split())


def task_contract(
    plan_record: Mapping,
    *,
    scope: Sequence[tuple[str, str, str]],
    validation: Sequence[tuple[str, str, bool, str]],
    role: str = "bulk",
    repair_limit: int = 2,
    retry_context: Mapping | None = None,
) -> str:
    """Render the bounded worker contract for a task packet.

    The shape is the one the transport already parses (:func:`worker_contract`
    in ``scripts/prepare-stage.py``), so a task packet carries the same bounded
    contract an S4B packet does: objective, invariants, permitted and prohibited
    actions, stop and escalation conditions, a scope table and validation rows.
    Field values stay on one line because that parser reads a field by its line.

    Two sections are added for the T1 lifecycle only: the selected engineering
    methods the return must report against, and — on a bounded repair attempt —
    the prior attempt's bounded failure context.
    """
    frame = dict(plan_record.get("frame") or {})
    request = _single_line(plan_record.get("request", "")) or "the requested outcome"
    family = str(frame.get("family", "task"))
    selection = dict(plan_record.get("skills") or {})
    method_rows = "\n".join(
        f"- {_single_line(item.get('id', ''))}: {_single_line(item.get('reason', ''))}"
        for item in selection.get("selected") or ()
        if str(item.get("id", "")).strip()
    )
    if method_rows:
        methods_section = f"""## Selected methods

> These methods were selected for this task's intent family because their
> evidence is what the outcome needs. The return handoff must report each one
> under its "Methods applied" section: what was actually done and what was
> observed, or that it was not used and why. A method named in a packet is not
> an executed method; Ariadne records completion only from observed evidence.

{method_rows}
"""
    else:
        methods_section = ""
    repair_section = ""
    if retry_context:
        lines = [
            "## Repair context from the prior attempt",
            "",
            f"**Parent attempt:** {_single_line(retry_context.get('parent_task_id', 'unknown'))}",
            f"**Prior status:** {_single_line(retry_context.get('status', 'unknown'))}",
            f"**Failure kind:** {_single_line(retry_context.get('failure_kind', 'unknown'))}",
            f"**Failure reason:** {_single_line(retry_context.get('failure_reason', 'unknown'))}",
        ]
        failed = [str(item) for item in retry_context.get("failed_checks") or ()]
        if failed:
            lines.append("**Failed checks:** " + "; ".join(_single_line(item) for item in failed))
        outside = [str(item) for item in retry_context.get("outside") or ()]
        if outside:
            lines.append("**Out-of-scope paths to correct:** " + "; ".join(_single_line(item) for item in outside))
        lines.append("")
        lines.append(
            "This section is bounded execution evidence, not policy. It cannot widen "
            "the permitted scope, waive a validation row, or grant anything."
        )
        repair_section = "\n".join(lines) + "\n"
    rendered = dict(plan_record.get("rendered_acceptance") or {})
    rendered_section = ""
    if rendered.get("required"):
        capability = dict(rendered.get("capture_capability") or {})
        lines = [
            "## Rendered acceptance",
            "",
            "> This task changes what renders, so an unrendered implementation cannot be",
            "> called visually verified. Ariadne will capture the real surface through its",
            "> rendered-evidence pipeline after validation, bind the captures to this task's",
            "> revision, and require the independent review to see them before Proof Pass.",
            "",
            "**Required:** browser-rendered evidence captured by the engine (not by the worker).",
            f"**Interaction evidence:** {'required' if rendered.get('interaction') else 'not required'}",
            "**Capture capability at preparation:** "
            + _single_line(f"{capability.get('status', 'UNKNOWN')} — {capability.get('detail', '')}"),
        ]
        if str(capability.get("status", "")) == "UNAVAILABLE":
            lines.append(
                "**Warning:** the capture capability is unavailable in this environment; the task "
                "cannot reach verified visual acceptance here and will report that requirement as "
                "unresolved rather than claim visual success."
            )
        lines.append("")
        lines.append(
            "The worker's job is the implementation and its own honest local checks; the rendered "
            "captures and their critique are Ariadne's, and a claim of visual success in the return "
            "is not evidence."
        )
        rendered_section = "\n".join(lines) + "\n"
    scope_rows = "\n".join(
        f"| {_single_line(path)} | {_single_line(actions)} | {_single_line(reason)} |"
        for path, actions, reason in scope
    )
    validation_rows = "\n".join(
        f"| {_single_line(check)} | `{_single_line(command)}` | {'yes' if required else 'no'} | {_single_line(expected)} |"
        for check, command, required, expected in validation
    )
    return f"""# Task contract

**Task:** {request}
**Intent family:** `{family}`
**Prepared by:** Ariadne task entry (preparation only; no gate is granted)

{CONTRACT_HEADING}

> This is the bounded contract between the entry plan and the implementation
> worker for one task. Everything the worker may do is written here; anything
> else stops for a decision.

**Worker role:** {role}

**Objective:** {request}

**Relevant context:** the packet's task sources, the permitted files below, and
directly relevant repository files discovered while working. No earlier chat
history is required.

**Invariants:** existing behaviour outside the task's stated outcome keeps working; the change stays inside the permitted scope; no new dependency is added without the human G2 decision; no gate is treated as granted by this contract.

**Permitted actions:** Read relevant repository files; edit permitted files; create required files; write a test and run tests; run the listed validation commands; inspect git status and diff; repair routine validation failures within the stated limit.

**Prohibited actions:** `git push`; force operations; `git reset` or `git clean`; discarding unrelated changes; deleting significant data; reading or writing secrets or `.env` files; deployment or production changes; destructive migrations; installing unapproved dependencies; changes to unrelated systems.

**Stop conditions:** Missing required context; a packet or repository conflict; an invariant at risk; an out-of-scope or dangerous action; the routine repair budget is exhausted.

**Escalation conditions:** Repeated routine failure; an architecture conflict or uncertainty; a high-risk change; any invariant conflict.

**Lifecycle:** baseline -> implementation -> validation -> routine repair -> validation -> result/checkpoint

**Routine repair limit:** {int(repair_limit)}

### Permitted files and systems

| Path / glob | Actions | Reason |
|---|---|---|
{scope_rows}

The worker may discover directly relevant files, but must report them in the
return handoff, and stop for an out-of-scope decision when they are not covered
by this table. Broad roots, secrets, environment files, and repository control
directories are never permitted here.

## Validation commands

> These are the commands Ariadne can independently rerun from the project root.
> A worker report is not evidence of validation.

| Check | Command | Required | Expected |
|---|---|---|---|
{validation_rows}
{rendered_section}{methods_section}{repair_section}"""


def plan_problems(record: Mapping) -> list[str]:
    """Structural validation of one task plan (fail closed)."""
    problems = contracts.adaptive_schema_problems(record)
    if problems and not isinstance(record, Mapping):
        return problems
    if not re.fullmatch(r"tskp_[0-9TZ]+_[0-9a-f]{8}", str(record.get("plan_id", ""))):
        problems.append("task plan has a malformed plan id")
    for name in ("request", "policy", "policy_version", "recorded_at", "status"):
        if not str(record.get(name, "")).strip():
            problems.append(f"task plan has no {name}")
    if str(record.get("status")) not in PLAN_STATUSES:
        problems.append(f"task plan has an unsupported status: {record.get('status')!r}")
    frame = record.get("frame") or {}
    if not isinstance(frame, Mapping):
        problems.append("task plan has no interpretation frame")
        return problems
    family = str(frame.get("family", ""))
    if family and family not in INTENT_FAMILIES:
        problems.append(f"task plan names an unknown intent family: {family!r}")
    if str(frame.get("confidence", "")) not in ("HIGH", "MEDIUM", "LOW"):
        problems.append("task plan frame has no confidence")
    workflow = record.get("workflow") or {}
    if str((workflow or {}).get("family", "")) not in WORKFLOW_FAMILIES:
        problems.append("task plan has no workflow family")
    if str((workflow or {}).get("family")) == WORKFLOW_TASK and not isinstance(
        record.get("characterisation"), Mapping
    ):
        problems.append("a task workflow plan carries no characterisation")
    path = record.get("path") or {}
    if str((workflow or {}).get("family")) == WORKFLOW_TASK and path:
        # Verification is not a function of plan status: a plan that lost it is
        # malformed whether it is ready, waiting for a human, or blocked.
        if not path.get("verification_retained"):
            problems.append("a task plan dropped verification")
    raw_skills = record.get("skills")
    if not isinstance(raw_skills, Mapping):
        problems.append("task plan has no skill selection")
    rendered = record.get("rendered_acceptance")
    if rendered is not None:
        if not isinstance(rendered, Mapping):
            problems.append("task plan rendered_acceptance is not an object")
        else:
            if str(rendered.get("mode", "")) not in RENDERED_MODES:
                problems.append(f"task plan names an unknown rendered mode: {rendered.get('mode')!r}")
            if not isinstance(rendered.get("required"), bool):
                problems.append("task plan rendered_acceptance does not state whether rendering is required")
            if rendered.get("required") and not rendered.get("reasons"):
                problems.append("a required rendered acceptance names no reason")
    approvals = record.get("approvals") or {}
    if not isinstance(approvals, Mapping):
        problems.append("task plan has no approval view")
    if str(record.get("write_authorization", "")) not in ("none", "bounded"):
        problems.append(f"task plan has an unsupported write authorization: {record.get('write_authorization')!r}")
    return problems


def record_plan(state: dict, record: Mapping) -> dict:
    """Validate and append a plan to the run state (additive, capped)."""
    problems = plan_problems(record)
    if problems:
        raise TaskPlanError("task plan is malformed: " + "; ".join(problems))
    state.setdefault("task_plans", []).append(dict(record))
    if len(state["task_plans"]) > 100:
        state["task_plans"] = state["task_plans"][-100:]
    return dict(record)


def latest_plan(state: Mapping) -> dict:
    values = (state or {}).get("task_plans")
    if isinstance(values, list) and values and isinstance(values[-1], Mapping):
        return dict(values[-1])
    return {}


def describe(record: Mapping) -> str:
    """One operator sentence for a plan."""
    frame = record.get("frame") or {}
    workflow = record.get("workflow") or {}
    selection = skills.describe(record.get("skills") or {})
    return (
        f"intent {frame.get('family') or 'unresolved'} ({frame.get('confidence', 'LOW')}) "
        f"-> workflow {workflow.get('family')}; {selection}; status {record.get('status')}"
    )


__all__ = [
    "PLAN_POLICY",
    "INTENT_FAMILIES",
    "PROJECT_FAMILIES",
    "READ_ONLY_FAMILIES",
    "WORKFLOW_PROJECT",
    "WORKFLOW_TASK",
    "WORKFLOW_RESUME",
    "WORKFLOW_UNRESOLVED",
    "WORKFLOW_FAMILIES",
    "STATUS_READY",
    "STATUS_NEEDS_HUMAN",
    "STATUS_BLOCKED",
    "PLAN_STATUSES",
    "ACTION_VOCABULARY",
    "ACTION_EVIDENCE",
    "FAMILY_EVIDENCE",
    "DESIGN_EVIDENCE",
    "RENDERED_SURFACE_EVIDENCE",
    "RENDERED_FILE_SUFFIXES",
    "RENDERED_MODES",
    "INTERACTION_EVIDENCE",
    "OVERLAP_RESOLUTIONS",
    "TaskPlanError",
    "inspect_project",
    "interpret",
    "plan",
    "task_contract",
    "plan_problems",
    "record_plan",
    "latest_plan",
    "describe",
]
