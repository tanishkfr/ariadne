"""Design task characterisation, direction records and requirement closure (AR-202D T1/T5/T6).

Three things live here.

**Characterisation.** Design depth is *selected*, not assumed. The engine reads
deterministic project/task evidence — the request text, the handoff's declared
scope rows, the locked design artefacts, the creative assessment, the component
and capture capabilities actually available — and answers each design question
with ``REQUIRED`` / ``OPTIONAL`` / ``NOT_REQUIRED`` / ``UNKNOWN`` plus the
evidence it used. A backend task selects no design work at all; a copy change is
not a high-depth design task; and the presence of front-end code in the
repository is *never* by itself a reason to run reference research.

**Direction.** A design direction is an executable constraint record, not a mood
board. It is created by the engine, approved only on the human channel through
the ``G1D`` gate, bound to a revision fingerprint of exactly its constraining
sections, and it expires the moment those sections change. An implementation
worker cannot create, approve or silently inherit one.

**Closure.** Every design requirement is traceable
``Requirement → decision → implementation → evidence``, and the evidence needed
to close it depends on the claim: a rendered or behavioural requirement cannot
be verified from source inspection, a source-level requirement may be, and an
``implemented`` mapping is not an observation. Stale evidence closes nothing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping, Sequence

from . import contracts, render as render_module, review as review_module
from .contracts import (
    DESIGN_CHARACTERISTIC_VALUES,
    DESIGN_DEPTHS,
    DESIGN_PIPELINE,
    DESIGN_REQUIREMENT_EVIDENCE,
    DESIGN_REQUIREMENT_STATES,
    PIPELINE_SELECTIONS,
    ContractError,
)

# --------------------------------------------------------------- vocabulary

FRONTEND_SUFFIXES = (
    ".html", ".htm", ".css", ".scss", ".sass", ".less", ".jsx", ".tsx", ".vue",
    ".svelte", ".astro", ".razor", ".erb", ".hbs", ".twig", ".php",
)
"""File suffixes whose *declared change scope* is evidence of interface work.

The suffix list is used against the handoff's permitted scope, never against the
repository: a repository full of front-end code proves nothing about this task.
"""

DESIGN_TOKENS = (
    "design", "ui", "ux", "interface", "layout", "landing", "page", "screen", "hero",
    "typography", "font", "colour", "color", "palette", "spacing", "grid", "component",
    "button", "form", "input", "nav", "navigation", "dashboard", "modal", "card", "icon",
    "illustration", "brand", "style", "css", "tailwind", "theme", "dark mode", "visual",
    "figma", "mockup", "wireframe", "pixel", "look and feel", "front-end", "frontend",
)

VISUAL_TOKENS = (
    "visual", "hero", "landing", "typography", "font", "colour", "color", "palette",
    "spacing", "grid", "layout", "css", "tailwind", "theme", "dark mode", "icon",
    "illustration", "brand", "logo", "screenshot", "mockup", "figma", "pixel", "contrast",
)

INTERACTION_TOKENS = (
    "interaction", "animate", "animation", "motion", "transition", "hover", "focus",
    "gesture", "drag", "scroll", "keyboard", "swipe", "carousel", "accordion", "tooltip",
    "dropdown", "state", "loading", "skeleton", "toast", "menu",
)

IA_TOKENS = (
    "information architecture", "navigation", "sitemap", "menu structure", "hierarchy",
    "content structure", "onboarding", "flow", "funnel", "information density",
)

CONTENT_TOKEN = ("copy", "headline", "microcopy", "empty state", "error message", "content", "cms")

REFERENCE_TOKENS = (
    "reference", "references", "inspiration", "benchmark", "competitor", "moodboard",
    "mood board", "pattern", "best in class", "similar site", "research the space",
)

ACCESSIBILITY_TOKENS = (
    "accessibility", "a11y", "wcag", "screen reader", "aria", "keyboard", "contrast",
    "reduced motion", "focus visible", "accessible",
)

RESPONSIVE_TOKENS = (
    "responsive", "breakpoint", "viewport", "320", "375", "390", "414", "768", "1024", "1280",
)

COMPONENT_TOKENS = (
    "component library", "design system", "component", "registry", "dependency", "library",
    "shadcn", "radix", "npm install", "package", "widget", "primitive",
)

HIGH_STAKES_TOKENS = (
    "production", "release", "customer", "payment", "checkout", "live", "public",
    "marketing site", "launch",
)

NON_UI_TOKENS = (
    "migration", "database", "schema", "api endpoint", "worker", "queue", "cron",
    "etl", "pipeline job", "cli", "server", "backend", "back-end", "terraform",
    "infrastructure", "log", "metrics", "index", "query",
)

INTERACTIVE_SCOPE_TOKENS = ("button", "form", "input", "nav", "menu", "modal", "dialog", "control", "select", "toggle")

SMALL_TOKENS = (
    "fix", "fixes", "tweak", "adjust", "nudge", "rename", "typo", "bump", "clean up",
    "small", "minor", "one-line", "quick", "polish the", "tidy",
)
"""Declared small-scale repair language."""

NEW_SURFACE_TOKENS = (
    "new page", "new screen", "new landing", "new flow", "build a", "build the", "create a",
    "redesign", "landing page", "from scratch", "new section", "new dashboard", "rebuild",
)
"""Declared new-surface language."""

STRONG_DESIGN_TOKENS = (
    "design", "ui", "ux", "interface", "redesign", "layout", "hero", "landing",
    "typography", "palette", "theme", "dark mode", "figma", "mockup", "wireframe",
    "brand", "spacing", "visual", "style guide", "component library", "front-end design",
)
"""Terms that declare design work in their own right rather than incidentally."""

TOKEN_SOURCES = "rule-derived"
DECLARED_SOURCE = "user-declared"


def _item(value: str, source: str, evidence: Sequence[str]) -> dict:
    return {
        "value": value,
        "source": source,
        "evidence": [str(text) for text in evidence if str(text).strip()],
    }


def _unknown(evidence: Sequence[str] = (), source: str = "not-observed") -> dict:
    return _item("UNKNOWN", source, evidence)


def require_value(value: str) -> str:
    if value not in DESIGN_CHARACTERISTIC_VALUES:
        raise ContractError(f"unsupported design characteristic value: {value!r}")
    return value


# --------------------------------------------------------- project evidence

def scope_text(transport, project: Path) -> tuple[list[list[str]], str]:
    """The declared permitted scope rows of the current handoff, if any."""
    contract = {}
    if transport is not None:
        path = Path(project) / "HANDOFF.md"
        if path.is_file():
            try:
                contract = transport.worker_contract(path.read_text(encoding="utf-8")) or {}
            except Exception:
                contract = {}
    rows = [[str(cell) for cell in row] for row in (contract.get("scope_rows") or [])]
    return rows, " ".join(" ".join(row) for row in rows).lower()


def touched_frontend(rows: Sequence[Sequence[str]]) -> list[str]:
    """Scope rows that name an interface artifact. Task evidence, not repository evidence."""
    hits = []
    for row in rows:
        text = " ".join(str(cell) for cell in row)
        lowered = text.lower()
        if any(suffix in lowered for suffix in FRONTEND_SUFFIXES) or any(
            token in lowered for token in ("component", "stylesheet", "template", "view", "screen", "page")
        ):
            hits.append(str(row[0]) if row else text.strip())
    return [item for item in hits if item]


def _read_text(path: Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def package_dependencies(project: Path) -> dict:
    """Declared front-end dependencies, read from the project manifest when present."""
    path = Path(project) / "package.json"
    if not path.is_file():
        return {}
    import json

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(value, dict):
        return {}
    merged: dict[str, str] = {}
    for key in ("dependencies", "devDependencies"):
        block = value.get(key)
        if isinstance(block, dict):
            merged.update({str(name): str(version) for name, version in block.items()})
    return merged


DESIGN_SYSTEM_MARKERS = (
    "tailwind.config.js", "tailwind.config.ts", "tailwind.config.cjs",
    "tokens.json", "design-tokens.json", "theme.ts", "theme.js", "theme.css",
    "styles/tokens.css", "src/styles/tokens.css", "design-system", "components/ui",
    "src/components/ui", "storybook",
)

DESIGN_SYSTEM_PACKAGES = (
    "tailwindcss", "shadcn", "@radix-ui/react", "radix-ui", "bootstrap", "chakra-ui",
    "@chakra-ui/react", "material-ui", "@mui/material", "antd", "mantine", "@mantine/core",
    "styled-components", "@emotion/react", "sass", "postcss", "vanilla-extract", "open-props",
)

PROJECT_WALK_EXCLUDED_DIRS = frozenset({
    ".git", ".hg", ".svn", ".ariadne", "node_modules", "bower_components", "vendor",
    "dist", "build", "out", ".next", ".nuxt", ".svelte-kit", ".cache", "coverage",
    ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".tox", "target",
    ".idea", ".vscode",
})
"""Directories the project scan never descends into.

They are dependencies, build output, caches or runtime state: they are not the
project's own design surface, they can be enormous, and enumerating them is how
a "scan the project" call becomes a whole-disk walk. The list is deliberately
explicit and deterministic rather than an ignore-file dialect. Names are matched
case-insensitively, because the filesystems this runtime targets (Windows and
default macOS) are: on a case-sensitive filesystem this can exclude a directory
whose name differs only by case, which is the safe direction for a
dependency/build exclusion.
"""

MAX_STYLESHEET_SCAN_DIRECTORIES = 2_000
"""Hard bound on directories the stylesheet scan descends into."""

MAX_STYLESHEET_SCAN_ENTRIES = 50_000
"""Hard bound on directory entries the stylesheet scan lists.

50 000 entries is far above any plausible project's own file count (dependencies,
build output and runtime state are pruned first), so a legitimate project is
scanned in full; the bound exists to stop a pathological single directory from
being listed and sorted in its entirety. Only the first 40 stylesheets are read
for custom properties, and at most :data:`MAX_STYLESHEETS` are collected.
"""

MAX_STYLESHEETS = 200
"""Bound on stylesheets collected; only the first 40 are read for custom properties."""


def _stylesheet_paths(project: Path) -> tuple[list[Path], bool]:
    """Deterministic, pruned, bounded scan for the project's stylesheets.

    ``os.walk`` with in-place ``dirnames`` filtering prunes excluded directories
    *before* they are enumerated (the old ``glob("**/*.css")`` walked them and
    filtered afterwards), results are sorted so two runs over the same tree
    agree, and symlinked/reparse-point directories are not followed so a link
    cannot walk the scan out of the project. Directories and their listings are
    counted against the bounds *before* a listing is sorted, so a pathological
    tree cannot make the scan do unbounded work. The boolean reports whether a
    bound stopped the scan, so the evidence can say so instead of implying
    completeness.
    """
    import os
    import stat as stat_module

    root = Path(project)
    excluded = {name.casefold() for name in PROJECT_WALK_EXCLUDED_DIRS}
    found: list[Path] = []
    visited_dirs = 0
    visited_entries = 0
    bounded = False
    for current, dirnames, filenames in os.walk(root):
        visited_dirs += 1
        if visited_dirs > MAX_STYLESHEET_SCAN_DIRECTORIES:
            bounded = True
            break
        listing = len(dirnames) + len(filenames)
        if visited_entries + listing > MAX_STYLESHEET_SCAN_ENTRIES:
            bounded = True
            break
        visited_entries += listing
        kept: list[str] = []
        for name in sorted(dirnames):
            if name.casefold() in excluded:
                continue
            candidate = Path(current) / name
            try:
                attributes = os.lstat(candidate).st_file_attributes
            except (OSError, AttributeError):
                attributes = 0
            if os.path.islink(candidate) or (attributes & getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
                continue
            kept.append(name)
        dirnames[:] = kept
        for name in sorted(filenames):
            if len(found) >= MAX_STYLESHEETS:
                bounded = True
                break
            if name.lower().endswith((".css", ".scss")):
                found.append(Path(current) / name)
        if bounded:
            break
    return sorted(found), bounded


def design_system_maturity(project: Path) -> dict:
    """Project design-system maturity from declared, inspectable project evidence."""
    project = Path(project)
    markers = [marker for marker in DESIGN_SYSTEM_MARKERS if (project / marker).exists()]
    package = package_dependencies(project)
    packages = sorted(name for name in package if any(name == dep or name.startswith(dep) for dep in DESIGN_SYSTEM_PACKAGES))
    stylesheets, bounded = _stylesheet_paths(project)
    custom_properties = 0
    for sheet in stylesheets[:40]:
        custom_properties += len(re.findall(r"--[a-z0-9-]+\s*:", _read_text(sheet), flags=re.IGNORECASE))
    if markers and (packages or custom_properties >= 8):
        value = "MATURE"
    elif markers or packages or custom_properties:
        value = "PARTIAL"
    elif stylesheets or (project / "DESIGN.md").is_file():
        value = "NONE"
    else:
        value = "UNKNOWN"
    return _item(value, "runtime-observed" if value != "UNKNOWN" else "not-observed", (
        (f"design-system markers present: {', '.join(markers[:5])}") if markers else "",
        (f"design-system packages declared: {', '.join(packages[:5])}") if packages else "",
        (f"{custom_properties} CSS custom propert{'y' if custom_properties == 1 else 'ies'} across {len(stylesheets)} stylesheet(s)")
        if stylesheets else "",
        (f"the stylesheet scan stopped at its bound after {len(stylesheets)} stylesheet(s); "
         "dependency, build and runtime directories were never entered") if bounded else "",
        "no design-system evidence was found in the project" if value in ("NONE", "UNKNOWN") else "",
    ))


def creative_assessment(project: Path) -> dict:
    """The creative ledger's assessment, when one exists. Read-only; never created here."""
    try:
        from . import policy

        creative = policy.tool("creative")
    except (ContractError, OSError):
        return {}
    try:
        ledger = creative.load_ledger(Path(project))
    except Exception:
        return {}
    if not isinstance(ledger, Mapping):
        return {}
    assessment = ledger.get("assessment")
    return dict(assessment) if isinstance(assessment, Mapping) else {}


def _dimension(assessment: Mapping, name: str) -> str:
    value = (assessment.get("characteristics") or {}).get(name)
    if isinstance(value, Mapping):
        return str(value.get("level", "") or "").upper()
    return ""


# --------------------------------------------------------- characterisation

def characterize(
    state: dict,
    *,
    project: Path,
    stage: str,
    request: str = "",
    task_id: str = "",
    transport=None,
    characterisation: Mapping | None = None,
    reference_adapters: Mapping | None = None,
    capture_adapters: Mapping | None = None,
    declared: Mapping | None = None,
) -> dict:
    """Derive the design characteristics of one task, with the evidence for each."""
    project = Path(project)
    text = str(request or state.get("request", "") or "")
    lowered = text.lower()
    rows, scope = scope_text(transport, project)
    frontend_rows = touched_frontend(rows)
    assessment = creative_assessment(project)
    design_doc = (project / "DESIGN.md")
    design_locked = design_doc.is_file() and "locked at g1" in _read_text(design_doc).lower()
    declared = dict(declared or {})
    notes: list[str] = []

    def declared_or(value: str, name: str) -> dict | None:
        raw = declared.get(name)
        if isinstance(raw, Mapping):
            return _item(require_value(str(raw.get("value", "")).upper()), DECLARED_SOURCE,
                         [str(item) for item in (raw.get("evidence") or [])])
        if isinstance(raw, str):
            return _item(require_value(raw.upper()), DECLARED_SOURCE, ("declared for this task",))
        return None

    def tokens(source: str, needle_tokens: Sequence[str]) -> list[str]:
        haystack = lowered if source == "request" else scope
        return [token for token in needle_tokens if token in haystack]

    design_hits = tokens("request", DESIGN_TOKENS) + [f"scope: {name}" for name in frontend_rows]
    non_ui_hits = tokens("request", NON_UI_TOKENS)
    visual_hits = tokens("request", VISUAL_TOKENS)
    interaction_hits = tokens("request", INTERACTION_TOKENS)
    ia_hits = tokens("request", IA_TOKENS)
    content_hits = tokens("request", CONTENT_TOKEN)
    reference_hits = tokens("request", REFERENCE_TOKENS)
    accessibility_hits = tokens("request", ACCESSIBILITY_TOKENS)
    responsive_hits = tokens("request", RESPONSIVE_TOKENS)
    component_hits = tokens("request", COMPONENT_TOKENS) + tokens("scope", COMPONENT_TOKENS)
    stakes_hits = tokens("request", HIGH_STAKES_TOKENS)
    strong_design_hits = tokens("request", STRONG_DESIGN_TOKENS)
    small_hits = tokens("request", SMALL_TOKENS)
    surface_hits = tokens("request", NEW_SURFACE_TOKENS)
    library_hits = tokens("request", ("library", "dependency", "npm install", "package", "registry", "shadcn", "radix"))

    visual_dependence = _dimension(assessment, "visual_dependence")
    reference_sensitivity = _dimension(assessment, "reference_sensitivity")
    generic_risk = _dimension(assessment, "generic_risk")
    interaction_complexity = _dimension(assessment, "interaction_complexity")
    technical_uncertainty = _dimension(assessment, "technical_uncertainty")
    novelty = _dimension(assessment, "novelty")
    capability_needs = [item for item in (assessment.get("capability_needs") or []) if isinstance(item, Mapping)]

    # ------------------------------------------------------- design required
    if surface_hits and not small_hits:
        scale_value = _item("NEW_SURFACE", TOKEN_SOURCES, (
            "the request declares a new or redesigned surface: " + ", ".join(sorted(set(surface_hits))[:5]),
        ))
    elif small_hits and len(rows) <= 2:
        scale_value = _item("SMALL", TOKEN_SOURCES, (
            "the request declares a bounded repair: " + ", ".join(sorted(set(small_hits))[:5]),
        ))
    elif small_hits and not rows:
        scale_value = _item("SMALL", TOKEN_SOURCES, (
            "the request declares a bounded repair: " + ", ".join(sorted(set(small_hits))[:5]),
        ))
    else:
        scale_value = _unknown(("nothing in the request declares how large the change is",))
    scale = str(scale_value["value"])

    design_value = declared_or("design", "design_task")
    design_evidence: list[str] = []
    if design_value is None:
        if stage in ("S3", "S4A"):
            design_value = _item("REQUIRED", TOKEN_SOURCES, (f"stage {stage} produces or plans design direction",))
        elif small_hits and not strong_design_hits and not content_hits and scale == "SMALL":
            design_value = _item(
                "REQUIRED", TOKEN_SOURCES,
                ("a bounded repair to a user-visible surface is design work",),
            )
        elif content_hits and not strong_design_hits and not visual_hits and not interaction_hits:
            design_value = _item(
                "OPTIONAL", TOKEN_SOURCES,
                ("the request changes user-visible copy rather than the interface",),
            )
        elif non_ui_hits and not design_hits:
            design_value = _item(
                "NOT_REQUIRED", TOKEN_SOURCES,
                ("the request declares non-interface work: " + ", ".join(sorted(set(non_ui_hits))[:6]),),
            )
        elif design_hits:
            design_value = _item("REQUIRED", TOKEN_SOURCES, (
                ("the request declares interface work: " + ", ".join(sorted(set(design_hits))[:8])),
            ))
        elif rows:
            design_value = _item("NOT_REQUIRED", TOKEN_SOURCES, (
                f"the declared scope names no interface artifact ({len(rows)} scope row(s))",
            ))
        else:
            design_value = _unknown(("no request text, scope or declaration is available",))
    design_required = str(design_value["value"]) != "NOT_REQUIRED"
    design_evidence = list(design_value["evidence"])

    # ------------------------------------------------- visual / interaction
    visual_value = declared_or("visual_design", "visual_design")
    if visual_value is None:
        if stage == "S3":
            visual_value = _item("REQUIRED", TOKEN_SOURCES, ("the design-direction stage produces the visual system",))
        elif visual_hits:
            visual_value = _item("REQUIRED", TOKEN_SOURCES, ("visual terms in the request: " + ", ".join(sorted(set(visual_hits))[:6]),))
        elif visual_dependence == "HIGH":
            visual_value = _item("REQUIRED", "runtime-observed", ("the creative assessment records high visual dependence",))
        elif visual_dependence in ("LOW", "MEDIUM"):
            visual_value = _item("OPTIONAL", "runtime-observed", (f"the creative assessment records {visual_dependence.lower()} visual dependence",))
        elif not design_required:
            visual_value = _item("NOT_REQUIRED", TOKEN_SOURCES, ("the task is not an interface task",))
        elif frontend_rows:
            visual_value = _item("OPTIONAL", TOKEN_SOURCES, (f"interface artifacts are in scope: {', '.join(frontend_rows[:3])}",))
        else:
            visual_value = _unknown(("no visual evidence is declared for this task",))

    interaction_value = declared_or("interaction_design", "interaction_design")
    if interaction_value is None:
        if interaction_hits:
            interaction_value = _item("REQUIRED", TOKEN_SOURCES, ("interaction terms in the request: " + ", ".join(sorted(set(interaction_hits))[:6]),))
        elif interaction_complexity == "HIGH":
            interaction_value = _item("REQUIRED", "runtime-observed", ("the creative assessment records high interaction complexity",))
        elif not design_required:
            interaction_value = _item("NOT_REQUIRED", TOKEN_SOURCES, ("the task is not an interface task",))
        elif any(token in scope for token in INTERACTIVE_SCOPE_TOKENS):
            interaction_value = _item("OPTIONAL", TOKEN_SOURCES, ("the declared scope touches an interactive control",))
        else:
            interaction_value = _unknown(("no interaction evidence is declared for this task",))

    ia_value = declared_or("information_architecture", "information_architecture")
    if ia_value is None:
        if ia_hits:
            ia_value = _item("REQUIRED", TOKEN_SOURCES, ("information-architecture terms in the request: " + ", ".join(sorted(set(ia_hits))[:5]),))
        elif not design_required:
            ia_value = _item("NOT_REQUIRED", TOKEN_SOURCES, ("the task is not an interface task",))
        else:
            ia_value = _item("OPTIONAL", TOKEN_SOURCES, ("structure is implied by the interface work",)) if rows else _unknown()

    content_value = declared_or("content_hierarchy", "content_hierarchy")
    if content_value is None:
        if content_hits:
            content_value = _item("REQUIRED", TOKEN_SOURCES, ("content terms in the request: " + ", ".join(sorted(set(content_hits))[:5]),))
        elif not design_required:
            content_value = _item("NOT_REQUIRED", TOKEN_SOURCES, ("the task is not an interface task",))
        else:
            content_value = _unknown()

    component_value = declared_or("component_research", "component_research")
    if component_value is None:
        if library_hits or component_hits:
            component_value = _item("REQUIRED", TOKEN_SOURCES, ("the request declares component or dependency work: " + ", ".join(sorted(set(component_hits + library_hits))[:5]),))
        elif scale == "SMALL":
            component_value = _item(
                "NOT_REQUIRED", TOKEN_SOURCES,
                ("a bounded repair reuses what the project already has",),
            )
        elif technical_uncertainty == "HIGH" or interaction_complexity == "HIGH":
            component_value = _item("REQUIRED", "runtime-observed", ("the creative assessment records high technical or interaction uncertainty",))
        elif capability_needs:
            component_value = _item("OPTIONAL", "runtime-observed", (f"{len(capability_needs)} capability need(s) recorded in the creative plan",))
        elif not design_required:
            component_value = _item("NOT_REQUIRED", TOKEN_SOURCES, ("the task is not an interface task",))
        else:
            component_value = _item("OPTIONAL", TOKEN_SOURCES, ("interface work may reuse or extend an existing component",))

    reference_value = declared_or("reference_research", "reference_research")
    if reference_value is None:
        if reference_hits:
            reference_value = _item("REQUIRED", TOKEN_SOURCES, ("the request declares reference research: " + ", ".join(sorted(set(reference_hits))[:5]),))
        elif scale == "SMALL":
            reference_value = _item(
                "NOT_REQUIRED", TOKEN_SOURCES,
                ("a bounded repair does not justify external reference research",),
            )
        elif generic_risk == "HIGH" or reference_sensitivity == "HIGH":
            reference_value = _item("REQUIRED", "runtime-observed", ("the creative assessment records high generic risk or high reference sensitivity",))
        elif not design_required:
            reference_value = _item("NOT_REQUIRED", TOKEN_SOURCES, ("the task is not an interface task",))
        elif visual_dependence == "HIGH" and (novelty == "HIGH" or stakes_hits):
            reference_value = _item("OPTIONAL", "runtime-observed", ("a new high-visual surface may benefit from reference research",))
        else:
            reference_value = _item("NOT_REQUIRED", TOKEN_SOURCES, (
                "no design work in this task justifies external reference research",
            ))

    rendered_value = declared_or("rendered_qa", "rendered_qa")
    if rendered_value is None:
        if scale == "SMALL" and frontend_rows:
            rendered_value = _item(
                "OPTIONAL", TOKEN_SOURCES,
                ("a bounded repair should be looked at, and is not a rendered deliverable",),
            )
        elif visual_dependence == "HIGH" and frontend_rows:
            rendered_value = _item("REQUIRED", "runtime-observed", ("high visual dependence with interface artifacts in the declared scope",))
        elif frontend_rows:
            rendered_value = _item("REQUIRED", TOKEN_SOURCES, (f"interface artifacts are in the declared scope: {', '.join(frontend_rows[:3])}",))
        elif str(visual_value["value"]) == "REQUIRED":
            rendered_value = _item("REQUIRED", TOKEN_SOURCES, ("the task produces a visual surface",))
        elif not design_required:
            rendered_value = _item("NOT_REQUIRED", TOKEN_SOURCES, ("the task produces nothing rendered",))
        else:
            rendered_value = _item("OPTIONAL", TOKEN_SOURCES, ("no interface artifact is in the declared scope",))

    accessibility_value = declared_or("accessibility_review", "accessibility_review")
    if accessibility_value is None:
        if accessibility_hits:
            accessibility_value = _item("REQUIRED", TOKEN_SOURCES, ("accessibility terms in the request: " + ", ".join(sorted(set(accessibility_hits))[:5]),))
        elif frontend_rows and any(token in scope for token in INTERACTIVE_SCOPE_TOKENS):
            accessibility_value = _item("REQUIRED", TOKEN_SOURCES, ("the declared scope touches an interactive control",))
        elif not design_required:
            accessibility_value = _item("NOT_REQUIRED", TOKEN_SOURCES, ("the task produces no user-visible interface",))
        else:
            accessibility_value = _item("OPTIONAL", TOKEN_SOURCES, ("interface work should remain operable",))

    responsive_value = declared_or("responsive_review", "responsive_review")
    if responsive_value is None:
        if responsive_hits:
            responsive_value = _item("REQUIRED", TOKEN_SOURCES, ("responsive terms in the request: " + ", ".join(sorted(set(responsive_hits))[:5]),))
        elif frontend_rows and any(token in scope for token in ("layout", "grid", "nav", "header", "footer", "page", "screen")):
            responsive_value = _item("REQUIRED", TOKEN_SOURCES, ("the declared scope changes layout-bearing artifacts",))
        elif not design_required:
            responsive_value = _item("NOT_REQUIRED", TOKEN_SOURCES, ("the task produces no layout",))
        else:
            responsive_value = _item("OPTIONAL", TOKEN_SOURCES, ("interface work should remain responsive",))

    # ------------------------------------------------------------- stakes
    if stakes_hits:
        stakes_value = _item("HIGH", TOKEN_SOURCES, ("the request declares launch-facing work: " + ", ".join(sorted(set(stakes_hits))[:5]),))
    elif design_locked and (generic_risk == "HIGH"):
        stakes_value = _item("HIGH", "runtime-observed", ("a locked direction with high generic risk",))
    elif not design_required:
        stakes_value = _item("LOW", TOKEN_SOURCES, ("the task produces no design surface",))
    elif scale == "SMALL":
        stakes_value = _item("LOW", TOKEN_SOURCES, ("a bounded repair to an existing surface",))
    elif str(visual_value["value"]) == "REQUIRED":
        stakes_value = _item("MEDIUM", TOKEN_SOURCES, ("the task produces a visual surface",))
    else:
        stakes_value = _unknown()

    maturity = design_system_maturity(project)
    reference_environment = {
        "adapters": {
            str(adapter_id): {
                "enabled": bool(getattr(adapter, "enabled", lambda: True)()),
                "capabilities": list(adapter.capabilities()),
            }
            for adapter_id, adapter in dict(reference_adapters or {}).items()
        },
    }
    capture_environment = {
        "adapters": {
            str(adapter_id): {
                "available": bool(adapter.available()[0]),
                "reason": str(adapter.available()[1]),
                "capabilities": list(adapter.capabilities()),
            }
            for adapter_id, adapter in dict(capture_adapters or {}).items()
        },
    }
    visual_evidence_possible = any(
        bool(item.get("available")) and "screenshot" in (item.get("capabilities") or [])
        for item in capture_environment["adapters"].values()
    )
    if str(rendered_value["value"]) == "REQUIRED" and not visual_evidence_possible:
        notes.append(
            "rendered QA is required but no capture adapter reports a screenshot capability; "
            "the requirement must be recorded unverified with its blocker rather than assumed"
        )
    if str(reference_value["value"]) == "REQUIRED" and not any(
        bool(item.get("enabled")) and "retrieve_content" in (item.get("capabilities") or [])
        for item in reference_environment["adapters"].values()
    ):
        notes.append(
            "reference research is required but no enabled adapter can retrieve content; "
            "attempts must be recorded inaccessible with their blocker"
        )

    record = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "characterisation_id": contracts.new_record_id("dch"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "stage": str(stage),
        "task_type": str((characterisation or {}).get("task_type", {}).get("value", "") or ""),
        "task_characterisation_id": str((characterisation or {}).get("characterisation_id", "")),
        "characteristics": {
            "design_task": design_value,
            "visual_design": visual_value,
            "interaction_design": interaction_value,
            "information_architecture": ia_value,
            "content_hierarchy": content_value,
            "component_research": component_value,
            "reference_research": reference_value,
            "rendered_qa": rendered_value,
            "accessibility_review": accessibility_value,
            "responsive_review": responsive_value,
            "design_stakes": stakes_value,
            "design_scale": scale_value,
            "novelty": _item(novelty or "UNKNOWN", "runtime-observed" if novelty else "not-observed",
                             ("the creative assessment records novelty",) if novelty else ()),
            "design_system_maturity": maturity,
        },
        "request_tokens": sorted({token for token in design_hits + visual_hits + interaction_hits + reference_hits}),
        "scope_rows": [[str(cell) for cell in row] for row in rows],
        "declared_scope": {
            "frontend_artifacts": frontend_rows,
            "rows": len(rows),
        },
        "creative_assessment": {
            "present": bool(assessment),
            "visual_dependence": visual_dependence,
            "reference_sensitivity": reference_sensitivity,
            "generic_risk": generic_risk,
            "interaction_complexity": interaction_complexity,
            "technical_uncertainty": technical_uncertainty,
            "novelty": novelty,
            "capability_needs": len(capability_needs),
        },
        "reference_environment": reference_environment,
        "capture_environment": capture_environment,
        "notes": notes,
        "policy_version": contracts.POLICY_VERSION,
        "recorded_at": contracts.utc_now(),
    }
    problems = characterisation_problems(record)
    if problems:
        raise ContractError("design characterisation is malformed: " + "; ".join(problems))
    return record


def characterisation_problems(record: Mapping) -> list[str]:
    problems = contracts.design_schema_problems(record)
    if not isinstance(record, Mapping):
        return problems
    if not contracts.design_id_matches("dch", str(record.get("characterisation_id", ""))):
        problems.append("design characterisation has a malformed id")
    characteristics = record.get("characteristics")
    if not isinstance(characteristics, Mapping) or not characteristics:
        problems.append("design characterisation has no characteristics")
        return list(dict.fromkeys(problems))
    for name, value in characteristics.items():
        if not isinstance(value, Mapping):
            problems.append(f"design characteristic {name} is malformed")
            continue
        if str(value.get("value", "")) not in contracts.DESIGN_CHARACTERISTIC_DOMAINS.get(
            str(name), DESIGN_CHARACTERISTIC_VALUES
        ):
            problems.append(f"design characteristic {name} has an unsupported value: {value.get('value')!r}")
        if not str(value.get("source", "")).strip():
            problems.append(f"design characteristic {name} does not record its source")
    for name in ("design_task", "visual_design", "reference_research", "rendered_qa"):
        if name not in characteristics:
            problems.append(f"design characterisation is missing the {name} characteristic")
    return list(dict.fromkeys(problems))


# ------------------------------------------------------------------- depth

def depth_of(record: Mapping) -> str:
    """Select the workflow depth from the characteristics. No numeric score."""
    values = {
        name: str((value or {}).get("value", "UNKNOWN"))
        for name, value in (record.get("characteristics") or {}).items()
    }
    if values.get("design_task") == "NOT_REQUIRED":
        return "NONE"
    if values.get("design_task") == "UNKNOWN":
        return "MINIMAL" if values.get("rendered_qa") in ("REQUIRED", "OPTIONAL") else "NONE"
    if values.get("design_scale") == "SMALL":
        # A bounded repair is design work; it is not a research project. Depth is
        # capped so a spacing fix never selects reference research or a critique.
        return "MINIMAL"
    research_required = sum(
        1 for name in ("reference_research", "component_research", "interaction_design", "information_architecture")
        if values.get(name) == "REQUIRED"
    )
    if values.get("reference_research") == "REQUIRED" and (
        values.get("design_stakes") in ("MEDIUM", "HIGH") or record.get("creative_assessment", {}).get("generic_risk") == "HIGH"
    ):
        return "DEEP"
    if research_required >= 2 or values.get("rendered_qa") == "REQUIRED":
        return "STANDARD"
    if values.get("visual_design") == "REQUIRED" or values.get("component_research") == "REQUIRED":
        return "STANDARD"
    return "MINIMAL"


def select_pipeline(record: Mapping) -> dict:
    """Per-stage selection with the evidence that selected it."""
    values = {
        name: str((value or {}).get("value", "UNKNOWN"))
        for name, value in (record.get("characteristics") or {}).items()
    }
    depth = depth_of(record)
    design = values.get("design_task")
    stages: dict[str, dict] = {}

    def put(stage: str, selection: str, reason: str) -> None:
        if stage not in DESIGN_PIPELINE:
            raise ContractError(f"unknown design pipeline stage: {stage!r}")
        if selection not in PIPELINE_SELECTIONS:
            raise ContractError(f"unknown pipeline selection: {selection!r}")
        stages[stage] = {"stage": stage, "selection": selection, "reason": reason}

    if design == "REQUIRED":
        put("UNDERSTAND", "REQUIRED", "the task is an interface design task")
    elif design == "OPTIONAL":
        put("UNDERSTAND", "OPTIONAL", "the task may touch user-visible surface")
    else:
        put("UNDERSTAND", "SKIPPED", "no design work is required for this task")

    research = values.get("reference_research")
    if research == "REQUIRED":
        put("RETRIEVE", "REQUIRED", "reference research is required by the task")
        put("INSPECT", "REQUIRED", "a retrieved reference must be inspected before it can inform anything")
        put("ANALYSE", "REQUIRED", "inspection must be generalised before it can influence the design")
    elif research == "OPTIONAL":
        put("RETRIEVE", "OPTIONAL", "reference research may help and is not required")
        put("INSPECT", "OPTIONAL", "only if a reference is actually retrieved")
        put("ANALYSE", "OPTIONAL", "only if a reference is actually inspected")
    else:
        reason = "reference research is not required for this task"
        put("RETRIEVE", "SKIPPED", reason)
        put("INSPECT", "SKIPPED", reason)
        put("ANALYSE", "SKIPPED", reason)

    if design == "NOT_REQUIRED":
        put("DIRECT", "SKIPPED", "the task produces no design direction")
    elif depth in ("STANDARD", "DEEP"):
        put("DIRECT", "REQUIRED", f"design depth {depth} requires an approved direction")
    else:
        put("DIRECT", "OPTIONAL", "design depth MINIMAL: a direction record is optional")

    if design == "NOT_REQUIRED":
        put("IMPLEMENT", "SKIPPED", "the task is not an interface task")
        put("OBSERVE", "SKIPPED", "nothing rendered is produced")
        put("CRITIQUE", "SKIPPED", "nothing rendered is produced")
        put("REFINE", "SKIPPED", "nothing rendered is produced")
        return {"depth": depth, "stages": stages, "selection_basis": "design task characterisation"}
    put("IMPLEMENT", "REQUIRED", "the task changes the project")

    rendered = values.get("rendered_qa")
    if rendered == "REQUIRED":
        put("OBSERVE", "REQUIRED", "a rendered requirement needs rendered evidence")
    elif rendered == "OPTIONAL":
        put("OBSERVE", "OPTIONAL", "rendered observation may help and is not required")
    else:
        put("OBSERVE", "SKIPPED", "the task declares no rendered requirement")

    if depth in ("STANDARD", "DEEP"):
        put("CRITIQUE", "REQUIRED", "substantial design work requires an independent critique")
        put("REFINE", "OPTIONAL", "refinement happens only in response to a recorded finding")
    elif rendered == "REQUIRED":
        put("CRITIQUE", "OPTIONAL", "small but rendered change: a critique may be selected")
        put("REFINE", "OPTIONAL", "refinement happens only in response to a recorded finding")
    else:
        put("CRITIQUE", "SKIPPED", "no independent critique is required at this depth")
        put("REFINE", "SKIPPED", "no critique, so no critique-driven refinement")
    return {"depth": depth, "stages": stages, "selection_basis": "design task characterisation"}


def record_characterisation(state: dict, record: Mapping) -> dict:
    problems = characterisation_problems(record)
    if problems:
        raise ContractError("design characterisation is malformed: " + "; ".join(problems))
    state.setdefault("design_characterisations", []).append(dict(record))
    if len(state["design_characterisations"]) > 200:
        state["design_characterisations"] = state["design_characterisations"][-200:]
    return dict(record)


def latest_characterisation(state: dict, *, task_id: str = "") -> dict:
    values = state.get("design_characterisations")
    if not isinstance(values, list):
        return {}
    rows = [item for item in values if isinstance(item, Mapping)]
    if task_id:
        rows = [item for item in rows if str(item.get("task_id", "")) == str(task_id)]
    return dict(rows[-1]) if rows else {}


def latest_plan(state: dict, *, task_id: str = "") -> dict:
    values = state.get("design_plans")
    if not isinstance(values, list):
        return {}
    rows = [item for item in values if isinstance(item, Mapping)]
    if task_id:
        rows = [item for item in rows if str(item.get("task_id", "")) == str(task_id)]
    return dict(rows[-1]) if rows else {}


def plan(state: dict, record: Mapping, *, task_id: str = "") -> dict:
    """Select and record the pipeline for a characterisation."""
    selection = select_pipeline(record)
    result = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "plan_id": contracts.new_record_id("dpl"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id or record.get("task_id", "")),
        "characterisation_id": str(record.get("characterisation_id", "")),
        "stage": str(record.get("stage", "")),
        "depth": selection["depth"],
        "stages": selection["stages"],
        "selection_basis": selection["selection_basis"],
        "policy_version": contracts.POLICY_VERSION,
        "recorded_at": contracts.utc_now(),
    }
    state.setdefault("design_plans", []).append(result)
    if len(state["design_plans"]) > 200:
        state["design_plans"] = state["design_plans"][-200:]
    return result


def stage_selection(record: Mapping, stage: str) -> str:
    selection = select_pipeline(record)
    return str((selection["stages"].get(stage) or {}).get("selection", "SKIPPED"))


def design_required(state: dict, *, task_id: str = "") -> bool:
    """Whether design work applies to this task. The single gate every caller uses."""
    record = latest_characterisation(state, task_id=task_id)
    if not record:
        record = latest_characterisation(state)
    value = str(((record.get("characteristics") or {}).get("design_task") or {}).get("value", ""))
    return value in ("REQUIRED", "OPTIONAL")


def reference_research_required(state: dict, *, task_id: str = "") -> bool:
    record = latest_characterisation(state, task_id=task_id)
    value = str(((record.get("characteristics") or {}).get("reference_research") or {}).get("value", ""))
    return value == "REQUIRED"


# -------------------------------------------------------------- direction

DIRECTION_SECTIONS = contracts.DIRECTION_SECTIONS
"""Every constraining section of a direction record. Each is a list of sentences.

Defined once in :mod:`ariadne_engine.contracts` so the record builder, the
structural validator and the approval fingerprint all read the same vocabulary.
"""

STATEMENT_RULES = re.compile(r"\b(when|while|at|on|if|before|after|within|above|below)\b", re.IGNORECASE)


def create_direction(
    state: dict,
    *,
    task_id: str,
    goal: str,
    scope: str,
    product_context: Sequence[str],
    key_hierarchy: Sequence[str],
    interaction_principles: Sequence[str],
    visual_principles: Sequence[str],
    content_principles: Sequence[str],
    constraints: Sequence[str],
    existing_system: Sequence[str] = (),
    reference_findings_adopted: Sequence[str] = (),
    findings_rejected: Sequence[str] = (),
    accessibility_requirements: Sequence[str] = (),
    responsive_requirements: Sequence[str] = (),
    approved_deviations: Sequence[str] = (),
    direction_id: str = "",
    supersedes: str = "",
    revision_hash: str = "",
) -> dict:
    """Create the engine's design-direction record. It is *unapproved* until G1D."""
    revision = str(revision_hash or "")
    if not revision:
        revision = _fallback_revision(state, scope)
    record = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "direction_id": str(direction_id or contracts.new_record_id("ddr")),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "goal": str(goal),
        "scope": str(scope),
        "revision_hash": revision,
        "product_context": _sentences(product_context),
        "key_hierarchy": _sentences(key_hierarchy),
        "interaction_principles": _sentences(interaction_principles),
        "visual_principles": _sentences(visual_principles),
        "content_principles": _sentences(content_principles),
        "constraints": _sentences(constraints),
        "existing_system": _sentences(existing_system),
        "reference_findings_adopted": _sentences(reference_findings_adopted),
        "findings_rejected": _sentences(findings_rejected),
        "accessibility_requirements": _sentences(accessibility_requirements),
        "responsive_requirements": _sentences(responsive_requirements),
        "approved_deviations": _sentences(approved_deviations),
        "statements": _statements(
            interaction_principles, responsive_requirements, key_hierarchy,
            visual_principles, content_principles, constraints, accessibility_requirements,
        ),
        "status": "candidate",
        "approval_id": "",
        "supersedes": str(supersedes),
        "recorded_at": contracts.utc_now(),
        "provenance": {"created_by": "engine", "policy_version": contracts.POLICY_VERSION},
    }
    problems = contracts.design_direction_problems(record)
    if problems:
        raise ContractError("design direction is malformed: " + "; ".join(problems))
    contracts.require_design_capacity(state, "design_directions")
    state.setdefault("design_directions", []).append(record)
    return record


def _sentences(values: Sequence[str]) -> list[str]:
    rows = []
    for value in values or ():
        text = " ".join(str(value).split())
        if text:
            rows.append(text)
    return rows


def _statements(*groups: Sequence[str]) -> list[dict]:
    rows: list[dict] = []
    for group in groups:
        for value in group or ():
            text = " ".join(str(value).split())
            if not text:
                continue
            rows.append({
                "value": text,
                "actionable": bool(STATEMENT_RULES.search(text)),
            })
    return rows


def _fallback_revision(state: dict, scope: str) -> str:
    return contracts.digest_fields("design-direction-record", {
        "direction-id": "unapproved",
        "task-id": str(state.get("run_id", "")),
        "scope": scope,
        "constrained-body": "created before any engine revision was recorded",
    })


def directions(state: dict) -> list[dict]:
    values = state.get("design_directions")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def direction(state: dict, direction_id: str) -> dict | None:
    for record in directions(state):
        if str(record.get("direction_id", "")) == str(direction_id):
            return record
    return None


def active_direction(state: dict, *, task_id: str = "") -> dict:
    """The most recent approved direction for a task, or ``{}``."""
    rows = [record for record in directions(state) if str(record.get("status", "")) == "approved"]
    if task_id:
        rows = [record for record in rows if str(record.get("task_id", "")) == str(task_id)]
    return dict(rows[-1]) if rows else {}


def latest_direction(state: dict, *, task_id: str = "") -> dict:
    """The most recent direction record for a task, approved or not.

    Used where the caller genuinely wants the candidate under review (to approve
    it), never to authorize implementation: authorization always goes through
    :func:`active_direction` and the ``G1D`` gate.
    """
    rows = [record for record in directions(state) if not task_id or str(record.get("task_id", "")) == str(task_id)]
    return dict(rows[-1]) if rows else {}


def direction_revision(record: Mapping) -> str:
    """Fingerprint of exactly the constraining content of a direction record."""
    return contracts.direction_fingerprint(record)


def direction_subject(record: Mapping) -> contracts.Subject:
    """The ``G1D`` subject an approval binds to: record, revision, task and scope."""
    revision = direction_revision(record)
    return contracts.Subject(
        subject_type="design-direction-record",
        subject_id=str(record.get("direction_id", "")),
        revision_hash=revision,
        detail=f"task {record.get('task_id')}: {record.get('goal', '')}",
        fields={
            "direction-id": str(record.get("direction_id", "")),
            "task-id": str(record.get("task_id", "")),
            "scope": str(record.get("scope", "")),
            "constrained-body": revision,
        },
    )


def approve_direction(
    state: dict,
    direction_id: str,
    *,
    identity: str,
    note: str = "",
    channel: str = contracts.APPROVAL_CHANNEL_HUMAN,
    stage: str = "",
    packet_id: str = "",
) -> dict:
    """Record the human approval of one direction record.

    The implementer cannot approve its own direction: the recorded identity may
    not be an identity already recorded as this task's worker, and only the
    human channel carries authority.
    """
    from . import policy

    record = direction(state, direction_id)
    if record is None:
        raise ContractError(f"no design-direction record matches {direction_id!r}")
    worker_ids = {value.lower() for value in review_module.worker_identities(state)}
    if str(identity or "").strip().lower() in worker_ids and str(identity or "").strip():
        raise ContractError(
            f"the recorded identity {identity!r} is the implementation worker for this run; "
            "an implementer cannot approve its own design direction"
        )
    subject = direction_subject(record)
    approval = policy.approve(
        state, "G1D", subject, identity, note, channel=channel, stage=stage, packet_id=packet_id,
    )
    record["status"] = "approved"
    record["approval_id"] = str(approval.get("approval_id", ""))
    record["approved_at"] = contracts.utc_now()
    return approval


def direction_problems(state: dict, *, task_id: str = "", require_approval: bool = True) -> list[str]:
    """Whether a usable approved direction exists for this task, and is still current."""
    problems: list[str] = []
    rows = [record for record in directions(state) if not task_id or str(record.get("task_id", "")) == str(task_id)]
    if not rows:
        problems.append(
            "no design-direction record exists for this task; substantive design work needs one "
            "before implementation (DESIGN_DIRECTION_MISSING)"
        )
        return problems
    record = rows[-1]
    problems.extend(contracts.design_direction_problems(record))
    if not require_approval:
        return list(dict.fromkeys(problems))
    from . import policy

    satisfied, reason = policy.gate_satisfied(state, "G1D", direction_subject(record))
    if not satisfied:
        problems.append(
            "the design direction is not approved for its current revision "
            "(DESIGN_DIRECTION_UNAPPROVED or DESIGN_DIRECTION_STALE): " + reason
        )
    return list(dict.fromkeys(problems))


# --------------------------------------------------------- requirement closure

def requirements(state: dict) -> list[dict]:
    values = state.get("design_requirements")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def requirement(state: dict, record_id: str) -> dict | None:
    for record in requirements(state):
        if str(record.get("record_id", "")) == str(record_id):
            return record
    return None


def current_requirement(state: dict, requirement_id: str) -> dict:
    rows = [record for record in requirements(state) if str(record.get("requirement_id", "")) == str(requirement_id)]
    return dict(rows[-1]) if rows else {}


def _evidence_strength_for(state: dict, evidence_ids: Sequence[str], *,
                           revision_hash: str = "") -> tuple[int, list[str], list[dict]]:
    """(strength, problems, used records) for a set of rendered-evidence ids.

    Currentness is decided by :func:`render.currentness_problems`, so this path
    and the staleness path can never disagree about the same record. An
    ``UNVERIFIED`` record is a problem here rather than a strength of zero: it
    means the observation was never made, and no closure may rest on it.
    """
    problems: list[str] = []
    best = -1
    used: list[dict] = []
    for evidence_id in evidence_ids:
        record = render_module.by_id(state, evidence_id)
        if record is None:
            problems.append(f"requirement cites unknown rendered evidence: {evidence_id}")
            continue
        currentness = render_module.currentness_problems(
            record, revision_hash=revision_hash, require_captured=True,
        )
        if currentness:
            problems.extend(f"{evidence_id}: {reason}" for reason in currentness)
            continue
        used.append(dict(record))
        best = max(best, render_module.strength(str(record.get("state", ""))))
    return best, problems, used


def record_requirement(
    state: dict,
    *,
    requirement_id: str,
    evidence_kind: str,
    task_id: str = "",
    decision: Mapping | None = None,
    implementation: Mapping | None = None,
    evidence_ids: Sequence[str] = (),
    state_name: str = "",
    rejection_reason: str = "",
    viewport: str = "",
    revision_hash: str = "",
    note: str = "",
) -> dict:
    """Record one closure state for a requirement, with the evidence that supports it.

    A state the evidence cannot support is refused rather than recorded: the
    engine will not write ``verified`` because someone asked for it.
    """
    if evidence_kind not in DESIGN_REQUIREMENT_EVIDENCE:
        raise ContractError(
            f"unsupported requirement evidence kind {evidence_kind!r}; expected "
            + ", ".join(DESIGN_REQUIREMENT_EVIDENCE)
        )
    decision_row = dict(decision or {})
    implementation_row = dict(implementation or {})
    if not decision_row:
        decision_row = {"summary": "not yet decided", "basis": ""}
    if state_name and state_name not in DESIGN_REQUIREMENT_STATES:
        raise ContractError(f"unsupported requirement state: {state_name!r}")

    best, evidence_problems, used = _evidence_strength_for(state, evidence_ids, revision_hash=revision_hash)
    resolved_state = str(state_name or "")
    if not resolved_state:
        if rejection_reason:
            resolved_state = "rejected"
        elif implementation_row.get("status") in ("implemented", "partial"):
            resolved_state = "implemented"
        elif decision_row.get("summary"):
            resolved_state = "planned"
        else:
            resolved_state = "unaddressed"
    problems: list[str] = []
    if resolved_state in ("observed", "verified"):
        if not used:
            problems.append(f"a {resolved_state} requirement must cite the evidence it was closed with")
        if evidence_problems:
            problems.extend(evidence_problems)
        minimum = render_module.strength("SOURCE_SUGGESTS") if evidence_kind == "source" else (
            2 if evidence_kind == "rendered" else 3
        )
        if best < minimum:
            problems.append(
                f"the cited evidence is too weak for an {evidence_kind} requirement to be {resolved_state}; "
                "a source suggestion is not a rendered observation and an implemented mapping is not evidence"
            )
        if resolved_state == "verified" and evidence_kind != "source" and best < render_module.strength("VERIFIED"):
            problems.append(
                "verifying a rendered or behavioural requirement needs independent re-production "
                "(rendered evidence in the VERIFIED state), not a first look"
            )
        if resolved_state == "verified" and evidence_kind == "source" and best < render_module.strength("VERIFIED"):
            independent = [
                record for record in (state.get("design_reviews") or [])
                if isinstance(record, Mapping) and str(record.get("outcome")) == "passed"
                and str(requirement_id) in {str(item) for item in (record.get("requirements") or [])}
            ]
            if not independent:
                problems.append(
                    "verifying a requirement without re-production needs an independent design review that "
                    "covers it; neither is recorded"
                )
    if resolved_state == "implemented" and not str(implementation_row.get("summary", "")).strip():
        problems.append("an implemented requirement must record what was implemented")
    if resolved_state == "rejected" and not str(rejection_reason or "").strip():
        problems.append("a rejected requirement must record why it was rejected")
    if problems:
        raise ContractError(
            f"requirement {requirement_id} cannot be recorded as {resolved_state}: " + "; ".join(problems)
        )

    record = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "record_id": contracts.new_record_id("drq"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "requirement_id": str(requirement_id),
        "evidence_kind": evidence_kind,
        "viewport": str(viewport),
        "revision_hash": str(revision_hash),
        "decision": decision_row,
        "implementation": implementation_row,
        "evidence": [str(item) for item in evidence_ids],
        "evidence_records": [
            {"evidence_id": record.get("evidence_id"), "state": record.get("state"), "kind": record.get("kind")}
            for record in used
        ],
        "state": resolved_state,
        "stale": False,
        "rejection_reason": str(rejection_reason),
        "note": str(note),
        "recorded_at": contracts.utc_now(),
        "provenance": {"created_by": "engine", "policy_version": contracts.POLICY_VERSION},
    }
    validated = contracts.design_requirement_problems(record)
    if validated:
        raise ContractError("design requirement is malformed: " + "; ".join(validated))
    contracts.require_design_capacity(state, "design_requirements")
    state.setdefault("design_requirements", []).append(record)
    return record


def requirement_closure(state: dict, requirement_id: str) -> str:
    """The current closure state of a requirement."""
    record = current_requirement(state, requirement_id)
    return str(record.get("state", "unaddressed")) if record else "unaddressed"


def stale_requirements(state: dict, *, revision_hash: str = "") -> list[dict]:
    """Requirements closed with evidence that no longer holds."""
    stale: list[dict] = []
    for record in requirements(state):
        if str(record.get("state")) not in ("observed", "verified", "implemented"):
            continue
        _, problems, _ = _evidence_strength_for(
            state, [str(item) for item in (record.get("evidence") or [])], revision_hash=revision_hash,
        )
        if problems:
            stale.append({
                "record_id": record.get("record_id"),
                "requirement_id": record.get("requirement_id"),
                "state": record.get("state"),
                "reasons": problems,
            })
    return stale


def requirement_problems(state: dict, required: Sequence[Mapping], *, revision_hash: str = "") -> list[str]:
    """Requirements that are required and not closed. Used by continuation gating."""
    problems: list[str] = []
    stale_ids = {str(item.get("requirement_id")) for item in stale_requirements(state, revision_hash=revision_hash)}
    for item in required:
        requirement_id = str(item.get("id", "") if isinstance(item, Mapping) else item)
        if not requirement_id:
            continue
        closure = requirement_closure(state, requirement_id)
        if closure in ("verified", "rejected"):
            continue
        if requirement_id in stale_ids:
            problems.append(
                f"design requirement {requirement_id} is {closure} but its evidence is stale; "
                "re-observe it before continuing"
            )
            continue
        problems.append(
            f"design requirement {requirement_id} is {closure}: it has not been closed with the "
            "evidence its claim needs"
        )
    return problems


# --------------------------------------------------------------- measurement

def measure(state: dict) -> dict:
    """Deterministic design-intelligence quantities. No invented quality score."""
    from . import components, references

    requirement_states = {value: 0 for value in DESIGN_REQUIREMENT_STATES}
    for record in requirements(state):
        key = str(record.get("state", ""))
        if key in requirement_states:
            requirement_states[key] += 1
    findings = [
        finding for record in (state.get("design_reviews") or [])
        if isinstance(record, Mapping)
        for finding in (record.get("findings") or []) if isinstance(finding, Mapping)
    ]
    finding_states: dict[str, int] = {}
    for finding in findings:
        key = str(finding.get("state", "open"))
        finding_states[key] = finding_states.get(key, 0) + 1
    refinements = [record for record in (state.get("design_refinements") or []) if isinstance(record, Mapping)]
    return {
        "references": references.summarise(state),
        "components": components.summarise(state),
        "requirements": {
            "tracked": len({str(record.get("requirement_id")) for record in requirements(state)}),
            "observed": requirement_states.get("observed", 0),
            "verified": requirement_states.get("verified", 0),
            "rejected": requirement_states.get("rejected", 0),
            "states": requirement_states,
        },
        "rendered_evidence": render_module.summarise(state),
        "critique": {
            "reviews": len([item for item in (state.get("design_reviews") or []) if isinstance(item, Mapping)]),
            "findings": len(findings),
            "finding_states": finding_states,
            "resolved": finding_states.get("repaired", 0) + finding_states.get("accepted", 0),
            "remaining": finding_states.get("open", 0) + finding_states.get("unresolved", 0),
        },
        "refinement": {
            "attempts": len(refinements),
            "verified": sum(1 for item in refinements if str(item.get("state")) == "verified"),
            "failed": sum(1 for item in refinements if str(item.get("state")) == "failed"),
            "regressions": sum(1 for item in refinements if item.get("regressions")),
        },
        "directions": {
            "records": len(directions(state)),
            "approved": len([item for item in directions(state) if str(item.get("status")) == "approved"]),
        },
        "characterisations": len([
            item for item in (state.get("design_characterisations") or []) if isinstance(item, Mapping)
        ]),
    }


def report(state: dict) -> dict:
    """The operator summary: what design work is tracked and what is unresolved."""
    record = latest_characterisation(state)
    selected = latest_plan(state)
    return {
        "design_task": bool(record),
        "depth": str(selected.get("depth", "")),
        "characteristics": {
            name: str((value or {}).get("value", ""))
            for name, value in ((record.get("characteristics") or {}).items())
        },
        "pipeline": {
            stage: str((value or {}).get("selection", ""))
            for stage, value in ((selected.get("stages") or {}).items())
        },
        "problems": structural_problems(state),
        "measurements": measure(state),
    }


def structural_problems(state: dict) -> list[str]:
    """Every structural problem in the design records of one run."""
    from . import components, critique, references

    problems: list[str] = []
    for record in state.get("design_characterisations") or []:
        if isinstance(record, Mapping):
            problems.extend(characterisation_problems(record))
    for item in directions(state):
        problems.extend(contracts.design_direction_problems(item))
    for item in requirements(state):
        problems.extend(contracts.design_requirement_problems(item))
    for item in (state.get("rendered_evidence") or []):
        if isinstance(item, Mapping):
            problems.extend(contracts.rendered_evidence_problems(item))
    for item in (state.get("design_reviews") or []):
        if isinstance(item, Mapping):
            problems.extend(contracts.design_review_problems(item))
    for item in (state.get("design_refinements") or []):
        if isinstance(item, Mapping):
            problems.extend(contracts.refinement_problems(item))
    problems.extend(references.provenance_problems(state))
    for item in components.candidates(state):
        problems.extend(contracts.component_candidate_problems(item))
    problems.extend(critique.finding_problems(state))
    return list(dict.fromkeys(problems))


__all__ = [
    "FRONTEND_SUFFIXES",
    "DESIGN_TOKENS",
    "VISUAL_TOKENS",
    "INTERACTION_TOKENS",
    "IA_TOKENS",
    "CONTENT_TOKEN",
    "REFERENCE_TOKENS",
    "ACCESSIBILITY_TOKENS",
    "RESPONSIVE_TOKENS",
    "COMPONENT_TOKENS",
    "NON_UI_TOKENS",
    "DIRECTION_SECTIONS",
    "characterize",
    "characterisation_problems",
    "record_characterisation",
    "latest_characterisation",
    "depth_of",
    "select_pipeline",
    "plan",
    "latest_plan",
    "stage_selection",
    "design_required",
    "reference_research_required",
    "scope_text",
    "touched_frontend",
    "design_system_maturity",
    "creative_assessment",
    "create_direction",
    "directions",
    "direction",
    "active_direction",
    "latest_direction",
    "direction_revision",
    "direction_subject",
    "approve_direction",
    "direction_problems",
    "requirements",
    "requirement",
    "current_requirement",
    "record_requirement",
    "requirement_closure",
    "stale_requirements",
    "requirement_problems",
    "measure",
    "report",
    "structural_problems",
]
