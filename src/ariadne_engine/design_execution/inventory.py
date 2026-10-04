"""Project-first component discovery, and the decision to reuse rather than generate.

> **Reuse what already exists before generating something new.**

A model asked to "build a panel" will happily write a new panel, and the result is
a repository with two panels, one of them the one people already use. That is not
a style problem, it is a correctness problem: the old one has the fix for the bug
found last month and the new one does not.

So the inventory runs *before* any component decision is made, and reads the
repository rather than asking anyone what it contains:

```text
tokens          CSS custom properties, Tailwind colours, font stacks
components      every component file, with the primitives it exports
primitives      buttons, forms, navigation, dialogs, panels, icons
layout          grid and stack utilities
motion          transition/keyframes utilities, reduced-motion handling
registry        any component registry or config the project declares
```

Four decisions are possible, in this order:

| Decision | When |
|---|---|
| ``REUSE_PROJECT_COMPONENT`` | the project already ships it, unchanged |
| ``ADAPT_PROJECT_COMPONENT`` | the project ships something close; it is extended, not replaced |
| ``USE_APPROVED_REGISTRY_COMPONENT`` | nothing local fits **and** an approval is recorded |
| ``BUILD_CUSTOM_COMPONENT`` | the fallback, and the one that must be justified |

The order is the decision procedure. External registries are last on purpose: a
registry is a *candidate source*, never the default, and the repository's own
``references/capabilities.json`` exists to make that explicit with
``install_authority: none â€” human G2 required``.

The module also holds the two boundaries that make reuse honest: the licence /
reuse-status record for any implementation reference, and the dependency-safety
path where a reference's use of a library becomes a request a human may refuse.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Mapping, Sequence

from .. import contracts
from ..contracts import ContractError
from ..design_reference import discovery as discovery_module
from ..design_reference import safety

COMPONENT_SUFFIXES = (".tsx", ".jsx", ".vue", ".svelte", ".ts", ".js")
"""Component file extensions worth reading.

``.ts``/``.js`` are included because a design system's primitives are frequently
plain modules - a splitter contract, a density helper, a class-name composer - and
a scan that only looked at ``.tsx`` would report "nothing here" for a project whose
entire UI layer is framework-free.
"""

PRIMITIVE_PATTERNS = {
    "buttons": (r"\b(Button|IconButton|ButtonGroup|Pressable)\b",),
    "forms": (r"\b(Form|Field|Input|Select|Checkbox|Radio|Switch|Textarea|Label)\b",),
    "navigation": (r"\b(Nav|NavItem|NavRail|Sidebar|Breadcrumb|Tabs|Menu|Bar)\w*\b",),
    "dialogs": (r"\b(Dialog|Modal|Sheet|Popover|Drawer|Overlay|AlertDialog)\b",),
    "panels": (r"\b(Panel|Split|Pane|Resizable|Splitter|Workspace|Inspector|SidePanel)\w*\b",),
    "icons": (r"\b(Icon|Logo|Avatar|Glyph|Symbol)\w*\b",),
    "toolbars": (r"\b(Toolbar|ToolBar|CommandBar|ActionBar)\b",),
    "typography": (r"\b(Text|Heading|Title|Label|Code|Truncat)\w*\b",),
}
"""Primitive families, found by *exported name* rather than by directory.

Naming a family ``buttons`` and finding ``Button`` in ``ui/controls.tsx`` is
evidence the project has a button; not finding it is not proof it lacks one, and the
record says which files were read so the negative result is checkable.
"""

EXPORT_RE = re.compile(
    r"(?:export\s+(?:default\s+)?(?:function|const|class|type|interface|enum)\s+([A-Za-z_$][\w$]*)"
    r"|export\s*\{([^}]*)\})"
)
CSS_UTILITY_RE = re.compile(r"^\s*\.([a-z][a-z0-9-]{2,40})\s*[,{]", re.MULTILINE)
KEYFRAMES_RE = re.compile(r"@(?:-webkit-)?keyframes\s+([\w-]+)")
REDUCED_MOTION_RE = re.compile(r"prefers-reduced-motion")
TRANSITION_RE = re.compile(r"(?:^|\s)transition(?:-[a-z-]+)?\s*:")
FONT_STACK_RE = re.compile(r"--font-([a-z-]+)\s*:\s*([^;}]+)")

MAX_COMPONENT_FILES = 400
MAX_PRIMITIVE_NAMES = 120
MAX_TOKEN_VALUES = 120

EXTRA_TOKEN_FILES = (
    "src/styles/tokens.css", "src/styles/theme.css", "src/styles/global.css",
    "src/lib/styles.css", "styles/global.css", "app/styles/tokens.css",
    "styles/variables.css", "src/css/tokens.css",
)
"""Token entry points AR-202D's list does not name.

AR-220's ``discovery.TOKEN_FILES`` covers the common React/Next/Vite placements. A
project that keeps its tokens at ``src/styles/tokens.css`` - which is where this
repository's own fixture keeps them - reported **zero** CSS variables from a file
sitting in a directory named ``styles``. That is not an exotic layout, and a scan
that misses it turns "this project has no tokens" into a false statement.
"""

EXTRA_COMPONENT_DIRS = (
    Path("src") / "lib", Path("src") / "app", Path("lib"), Path("app") / "lib",
    Path("src") / "views", Path("src") / "widgets",
)
"""Component locations the declared list does not name, for the same reason."""

FALLBACK_SCAN_DEPTH = 2
"""How deep the fallback component scan descends when the declared directories miss.

Bounded rather than recursive: an unbounded walk of a repository with a ``vendor`` or
``fixtures`` tree is a way to spend a minute reading files that are not components.
"""

SKIP_DIRS = {".git", "node_modules", "dist", "build", "coverage", "__pycache__", ".next", ".ariadne"}
"""Directories an inventory never walks.

``node_modules`` is the important one: it contains other people's components, and
counting them as the project's own is exactly the confusion this module exists to
prevent.
"""


def _bounded(project: Path, relative: str) -> Path | None:
    try:
        return safety.contained_path(relative, project, label=f"inventory path {relative}")
    except ContractError:
        return None


def _read(path: Path, *, limit: int = 262_144) -> str:
    try:
        raw = path.read_bytes()[:limit]
    except OSError:
        return ""
    return raw.decode("utf-8", errors="replace")


def inventory(project: Path | str) -> dict:
    """Read the project and report what it already provides.

    Read-only and offline. It walks declared component directories and reads files
    by name; it does not run a build, resolve a dependency graph, contact a
    registry or install anything.
    """
    root = Path(project)
    if not root.is_dir():
        raise ContractError(f"a component inventory needs a project directory: {root}")

    tokens = _tokens(root)
    components, scanned, skipped, search = _components(root)
    primitives = _primitives(components)
    layout = _layout(root)
    motion = _motion(root)
    registry = _registry(root)
    font_stacks = _font_stacks(root)

    return {
        "project_root": str(root),
        "tokens": tokens,
        "components": components,
        "component_files_scanned": scanned,
        "directories_skipped": sorted(skipped),
        "search": search,
        "primitives": primitives,
        "layout": layout,
        "motion": motion,
        "font_stacks": font_stacks,
        "registry": registry,
        "project_identity": {
            "design_documents": [
                {"kind": "DESIGN_DOCUMENT", "path": row["path"], "bytes": row["bytes"], "sha256": row["sha256"]}
                for row in discovery_module.discover_design_documents(root)
            ],
            "design_tokens": discovery_module.discover_tokens(root),
        },
        "probes": [
            "design_tokens", "component_files", "primitive_exports",
            "layout_utilities", "motion_utilities", "component_registry", "font_stacks",
        ],
        "note": (
            "an inventory is evidence about the repository as it is, not a design opinion. A family "
            "reported absent was looked for by exported name and is absent under the names searched"
        ),
    }


def _token_files() -> tuple[str, ...]:
    """Declared token entry points, AR-202D's list plus the ones it does not name."""
    ordered: list[str] = []
    for relative in tuple(discovery_module.TOKEN_FILES) + EXTRA_TOKEN_FILES:
        if relative not in ordered:
            ordered.append(relative)
    return tuple(ordered)


def _tokens(project: Path) -> dict:
    found = discovery_module.discover_tokens(project)
    variables: dict[str, str] = {}
    read_files: list[str] = []
    for relative in _token_files():
        path = _bounded(project, relative)
        if path is None or not path.is_file():
            continue
        read_files.append(relative)
        text = _read(path)
        for name, value in discovery_module.CSS_VARIABLE_RE.findall(text):
            if len(variables) < MAX_TOKEN_VALUES:
                variables[name] = value.strip()
    groups: dict[str, list[str]] = {}
    for name in sorted(variables):
        groups.setdefault(_token_group(name), []).append(name)
    return {
        "files": sorted(set(read_files) or list(found.get("files") or [])),
        "css_variable_count": len(variables) or int(found.get("css_variable_count", 0) or 0),
        "css_variables": variables,
        "groups": {group: names[:MAX_TOKEN_VALUES] for group, names in sorted(groups.items())},
        "tailwind_colour_keys": list(found.get("tailwind_colour_keys") or [])[:MAX_TOKEN_VALUES],
        "found": bool(variables) or bool(found.get("found")),
    }


def _token_group(name: str) -> str:
    """Group a token name into the identity slot it occupies.

    The grouping is what lets the plan say *the project's accent colour* rather
    than quoting a hex value, which is the difference between sourcing colour from
    identity and copying it from a reference.
    """
    lowered = str(name).lower()
    for group, needles in (
        ("accent", ("accent", "brand", "primary")),
        ("surface", ("canvas", "surface", "background", "bg-", "panel", "card")),
        ("text", ("text", "fg", "foreground", "ink", "label")),
        ("border", ("border", "hairline", "stroke", "divider", "separator")),
        ("radius", ("radius", "rounded", "corner")),
        ("spacing", ("space", "gap", "inset", "padding")),
        ("font", ("font", "type-", "leading", "tracking", "size")),
        ("motion", ("duration", "ease", "motion", "transition", "spring")),
    ):
        if any(needle in lowered for needle in needles):
            return group
    return "other"


def _components(project: Path) -> tuple[list[dict], int, set[str], dict]:
    """Read component files from the declared directories, then a bounded fallback.

    Declared first, so the common layouts are cheap and predictable. When they yield
    nothing, a shallow scan of ``src`` runs instead - because "no component files" is
    the most consequential false answer this module can give, since it turns every
    reuse decision into BUILD_CUSTOM. The fallback is recorded rather than hidden.
    """
    rows: list[dict] = []
    scanned = 0
    skipped: set[str] = set()
    searched: list[str] = []
    for relative in tuple(discovery_module.COMPONENT_DIRS) + EXTRA_COMPONENT_DIRS:
        directory = _bounded(project, relative.as_posix())
        if directory is None or not directory.is_dir():
            continue
        searched.append(relative.as_posix())
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in COMPONENT_SUFFIXES:
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(project).parts):
                skipped.update(SKIP_DIRS & set(path.relative_to(project).parts))
                continue
            if len(rows) >= MAX_COMPONENT_FILES:
                break
            scanned += 1
            rows.append(_component_row(project, path))
    fallback = False
    if not rows:
        source = _bounded(project, "src")
        if source is not None and source.is_dir():
            fallback = True
            for path in sorted(source.rglob("*")):
                relative = path.relative_to(project)
                if len(relative.parts) > FALLBACK_SCAN_DEPTH:
                    continue
                if not path.is_file() or path.suffix.lower() not in COMPONENT_SUFFIXES:
                    continue
                if any(part in SKIP_DIRS for part in relative.parts):
                    skipped.update(SKIP_DIRS & set(relative.parts))
                    continue
                if len(rows) >= MAX_COMPONENT_FILES:
                    break
                searched.append(relative.as_posix())
                scanned += 1
                rows.append(_component_row(project, path))
    return rows, scanned, skipped, {
        "declared_directories_searched": searched,
        "fallback_scan_used": fallback,
        "fallback_depth": FALLBACK_SCAN_DEPTH,
    }


def _component_row(project: Path, path: Path) -> dict:
    raw = _read(path)
    names = _exports(raw)
    return {
        "path": path.relative_to(project).as_posix(),
        "bytes": len(raw.encode("utf-8", "replace")),
        "sha256": hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest(),
        "exports": names[:MAX_PRIMITIVE_NAMES],
        "export_count": len(names),
        "primitives": sorted({family for family, found in _primitive_hits(names).items() if found}),
        "uses_tokens": sorted(set(re.findall(r"var\(\s*(--[A-Za-z0-9_-]+)", raw)))[:40],
    }


def _exports(text: str) -> list[str]:
    names: list[str] = []
    for match in EXPORT_RE.finditer(text):
        if match.group(1):
            names.append(match.group(1))
            continue
        for item in (match.group(2) or "").split(","):
            name = item.strip().split(" as ")[-1].strip()
            if name:
                names.append(name)
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def _primitive_hits(names: Sequence[str]) -> dict[str, bool]:
    hits = {family: False for family in PRIMITIVE_PATTERNS}
    for name in names:
        for family, patterns in PRIMITIVE_PATTERNS.items():
            if hits[family]:
                continue
            if any(re.search(pattern, name) for pattern in patterns):
                hits[family] = True
    return hits


def _primitives(components: Sequence[Mapping]) -> dict:
    found: dict[str, list[str]] = {}
    for row in components:
        for family in row.get("primitives") or []:
            found.setdefault(str(family), []).append(str(row.get("path", "")))
    return {
        "families": {family: paths[:20] for family, paths in sorted(found.items())},
        "present": sorted(found),
        "absent": sorted(set(PRIMITIVE_PATTERNS) - set(found)),
        "total_components": len(components),
    }


def _layout(project: Path) -> dict:
    classes: set[str] = set()
    files: list[str] = []
    for relative in ("src/styles", "styles", "app/globals.css", "src/app/globals.css"):
        path = _bounded(project, relative)
        if path is None or not path.is_file():
            continue
        files.append(relative)
        classes.update(CSS_UTILITY_RE.findall(_read(path)))
    for relative in ("tailwind.config.js", "tailwind.config.ts", "app/tailwind.config.ts"):
        path = _bounded(project, relative)
        if path is None or not path.is_file():
            continue
        files.append(relative)
        classes.update(re.findall(r"['\"]([\w./\[\]-]{2,40})['\"]\s*:", _read(path)))
    grid = sorted(name for name in classes if name.startswith(("grid", "col-", "layout", "stack")))
    return {
        "utility_classes_found": len(classes),
        "layout_utilities": grid[:60],
        "has_layout_system": bool(grid),
        "files": files,
    }


def _motion(project: Path) -> dict:
    keyframes: set[str] = set()
    reduced_motion = False
    transitions = 0
    for relative in ("src/styles", "styles", "app/globals.css", "src/app/globals.css"):
        path = _bounded(project, relative)
        if path is None or not path.is_dir():
            continue
        for candidate in sorted(path.rglob("*.css")):
            text = _read(candidate)
            keyframes.update(KEYFRAMES_RE.findall(text))
            reduced_motion = reduced_motion or bool(REDUCED_MOTION_RE.search(text))
            transitions += len(TRANSITION_RE.findall(text))
    tokens = []
    for relative in discovery_module.TOKEN_FILES:
        path = _bounded(project, relative)
        if path is not None and path.is_file():
            tokens.extend(f"--{name}" for name, _value in FONT_STACK_RE.findall(_read(path)))
    return {
        "keyframes": sorted(keyframes)[:40],
        "transition_declarations": transitions,
        "reduced_motion_handled": reduced_motion,
        "motion_token_candidates": sorted(set(tokens))[:20],
        "has_motion_system": bool(keyframes) or transitions > 0,
    }


def _font_stacks(project: Path) -> list[str]:
    stacks: dict[str, str] = {}
    for relative in discovery_module.TOKEN_FILES:
        path = _bounded(project, relative)
        if path is None or not path.is_file():
            continue
        for name, value in FONT_STACK_RE.findall(_read(path)):
            stacks[name] = value.strip()
    return [f"--font-{name}: {value}" for name, value in sorted(stacks.items())][:20]


def _registry(project: Path) -> dict:
    """Whatever component registry or config the project declares, read-only.

    Reports what is declared and explicitly does not resolve, fetch or install. A
    registry that would need a network call or a package manager is recorded as
    declared-but-unavailable, which is a first-class answer rather than a failure.
    """
    path = _bounded(project, "components.json")
    entries: list[str] = []
    declared = False
    if path is not None and path.is_file():
        declared = True
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "declared": True, "available": False, "entries": [],
                "reason": f"the declared component registry is malformed: {exc}",
                "install_authority": "none â€” human G2 required",
            }
        items = payload.get("items") if isinstance(payload, Mapping) else None
        entries = [str(row.get("name", "")) for row in items or [] if isinstance(row, Mapping)][:60]
    library = _bounded(project, "references/capabilities.json")
    candidates: list[str] = []
    if library is not None and library.is_file():
        try:
            payload = json.loads(library.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        for row in (payload.get("entries") if isinstance(payload, Mapping) else None) or []:
            if isinstance(row, Mapping):
                candidates.append(str(row.get("name", "")))
    return {
        "declared": declared,
        "available": False,
        "entries": entries,
        "local_candidates": candidates[:40],
        "reason": (
            "a project component registry is a candidate source. Ariadne reads its declaration and "
            "never resolves, downloads or installs from it; a component from a registry needs a "
            "recorded human approval like any other dependency"
        ),
        "install_authority": "none â€” human G2 required",
    }


# ------------------------------------------------------------------- decisions

def decide_reuse(
    *,
    need: str,
    found: Mapping,
    approved_registry_approvals: Mapping[str, str] | None = None,
    project_gap: str = "",
    existing_component: str = "",
) -> dict:
    """Decide how one required primitive will be obtained, and say why.

    The decision procedure is the ladder, evaluated in order, and the reason is
    the rung that answered it. There is no configuration that skips the ladder: a
    caller who wants an external registry component has to have found nothing local
    first, and has to hold the approval.
    """
    if not str(need).strip():
        raise ContractError("a component reuse decision must name the need it answers")
    families = found.get("primitives") if isinstance(found.get("primitives"), Mapping) else {}
    components = found.get("components") if isinstance(found.get("components"), list) else []
    approvals = dict(approved_registry_approvals or {})

    candidates = [
        row for row in components
        if isinstance(row, Mapping) and need.lower() in {str(name).lower() for name in row.get("exports") or []}
    ]
    if not candidates:
        lowered = need.lower()
        candidates = [
            row for row in components
            if isinstance(row, Mapping) and any(
                lowered in str(name).lower() for name in row.get("exports") or []
            )
        ]
    family_hit = [
        str(row.get("path", "")) for row in components
        if isinstance(row, Mapping) and str(need).lower() in {
            str(item).lower() for item in row.get("primitives") or []
        }
    ]

    if candidates:
        return {
            "need": str(need),
            "decision": "REUSE_PROJECT_COMPONENT",
            "existing_component": str(candidates[0].get("path", existing_component)),
            "exports": list(candidates[0].get("exports") or [])[:20],
            "reason": (
                f"the project already ships {candidates[0].get('path')} exporting "
                f"{need}; generating a replacement would leave two implementations of one primitive"
            ),
            "rung": "existing-project-component",
            "replacement_refused": "an existing project component is never replaced without a recorded reason",
        }
    if family_hit:
        return {
            "need": str(need),
            "decision": "ADAPT_PROJECT_COMPONENT",
            "existing_component": family_hit[0],
            "reason": (
                f"the project ships a related primitive in {family_hit[0]}; it is extended to cover the "
                f"need rather than replaced"
            ),
            "rung": "existing-project-component",
            "project_gap": str(project_gap),
        }
    approval_id = str(approvals.get(str(need), "")).strip()
    if approval_id:
        return {
            "need": str(need),
            "decision": "USE_APPROVED_REGISTRY_COMPONENT",
            "existing_component": "",
            "reason": (
                "nothing in the project answers this need, an approved registry entry does, and a "
                f"human approval ({approval_id}) is recorded for it"
            ),
            "rung": "approved-registry",
            "approval_id": approval_id,
            "install_authority": "none â€” human G2 required",
        }
    return {
        "need": str(need),
        "decision": "BUILD_CUSTOM_COMPONENT",
        "existing_component": "",
        "reason": (
            f"the project provides no {need}"
            + (f": {project_gap}" if str(project_gap).strip() else "")
            + ". No approved registry entry covers it either, so it is built inside the project and "
            "must use the project's own tokens"
        ),
        "rung": "project-local-implementation",
        "install_authority": "none â€” human G2 required",
        "registry_refused": (
            "no registry component was selected because no approval is recorded; a registry is a "
            "candidate source, not a default"
        ),
    }


def record_inventory(
    state: dict,
    *,
    task_id: str,
    project_root: str,
    found: Mapping,
    needs: Sequence[str] = (),
    approved_registry_approvals: Mapping[str, str] | None = None,
    recorded_at: str = "",
    inventory_id: str = "",
) -> dict:
    """Validate and append one inventory record with its reuse decisions."""
    decisions = [
        decide_reuse(
            need=str(need),
            found=found,
            approved_registry_approvals=approved_registry_approvals,
            project_gap=str(need),
        )
        for need in needs
        if str(need).strip()
    ]
    record = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "inventory_id": str(inventory_id or contracts.new_record_id("dci")),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "project_root": str(project_root),
        "recorded_at": str(recorded_at or contracts.utc_now()),
        "probes": list(found.get("probes") or []),
        "components": [dict(row) for row in found.get("components") or [] if isinstance(row, Mapping)],
        "component_files_scanned": int(found.get("component_files_scanned", 0) or 0),
        "search": dict(found.get("search") or {}),
        "tokens": dict(found.get("tokens") or {}) if isinstance(found.get("tokens"), Mapping) else {},
        "primitives": dict(found.get("primitives") or {}) if isinstance(found.get("primitives"), Mapping) else {},
        "layout": dict(found.get("layout") or {}) if isinstance(found.get("layout"), Mapping) else {},
"motion": dict(found.get("motion") or {}) if isinstance(found.get("motion"), Mapping) else {},
    "font_stacks": list(found.get("font_stacks") or []),
    "registry": dict(found.get("registry") or {}) if isinstance(found.get("registry"), Mapping) else {},
        "reuse_decisions": decisions,
        "note": str(found.get("note", "")),
        "provenance": {"created_by": "engine", "policy_version": contracts.POLICY_VERSION},
    }
    problems = contracts.component_inventory_problems(record)
    if problems:
        raise ContractError("component inventory is malformed: " + "; ".join(problems))
    contracts.require_design_capacity(state, "design_component_inventories")
    state.setdefault("design_component_inventories", []).append(record)
    return record


def inventories(state: Mapping) -> list[dict]:
    values = state.get("design_component_inventories")
    if not isinstance(values, list):
        return []
    return [dict(item) for item in values if isinstance(item, Mapping)]


def latest_inventory(state: Mapping, *, task_id: str = "") -> dict:
    rows = [
        record for record in inventories(state)
        if not task_id or str(record.get("task_id", "")) == str(task_id)
    ]
    return rows[-1] if rows else {}


# --------------------------------------------------------- licence and reuse

def implementation_reference(
    *,
    source: str,
    license_name: str,
    revision: str,
    files_inspected: Sequence[str],
    reuse_status: str,
    attribution_required: str = "",
    aesthetic_inherited: bool = False,
    reference_id: str = "",
    pattern: str = "",
) -> dict:
    """Record what may be done with an inspected implementation reference.

    ``UNKNOWN`` is a real answer and the least convenient one. A reference whose
    licence nobody recorded cannot be copied, and saying so here is what keeps the
    decision "adapt the idea, write the code in this project" separate from
    "paste the source", which is the distinction the whole record exists to keep.
    """
    if reuse_status not in contracts.REUSE_STATUSES:
        raise ContractError(f"unknown reuse status: {reuse_status}")
    if reuse_status in ("REUSE_ALLOWED", "REUSE_WITH_ATTRIBUTION") and not str(license_name).strip():
        raise ContractError(
            f"reuse status {reuse_status} requires a named licence; reuse permission without a licence "
            "is a guess"
        )
    if reuse_status == "REUSE_WITH_ATTRIBUTION" and not str(attribution_required).strip():
        raise ContractError(
            "REUSE_WITH_ATTRIBUTION requires the attribution text the licence actually demands; "
            "an empty attribution requirement is no requirement"
        )
    return {
        "reference_id": str(reference_id),
        "source": str(source),
        "license": str(license_name),
        "revision": str(revision),
        "files_inspected": [str(item) for item in files_inspected],
        "reuse_status": reuse_status,
        "attribution_required": str(attribution_required),
        "aesthetic_inherited": bool(aesthetic_inherited),
        "pattern": str(pattern),
        "code_copied": False,
        "note": (
            "using an implementation pattern does not adopt its source's aesthetic. A reference may be "
            "INSPECT_ONLY and still be the best available answer to a structural question"
        ),
    }


def reference_problems(reference: Mapping) -> list[str]:
    """Validate one implementation-reference record."""
    problems: list[str] = []
    status = str(reference.get("reuse_status", ""))
    if status not in contracts.REUSE_STATUSES:
        problems.append(f"implementation reference has an unknown reuse status: {status or 'missing'}")
    if not str(reference.get("source", "")).strip():
        problems.append("an implementation reference must name its source")
    if status in ("REUSE_ALLOWED", "REUSE_WITH_ATTRIBUTION") and not str(reference.get("license", "")).strip():
        problems.append(f"reuse status {status} requires a named licence")
    if status == "REUSE_WITH_ATTRIBUTION" and not str(reference.get("attribution_required", "")).strip():
        problems.append("REUSE_WITH_ATTRIBUTION requires the attribution the licence demands")
    if not str(reference.get("revision", "")).strip():
        problems.append("an implementation reference must record the revision it was inspected at")
    if not reference.get("files_inspected"):
        problems.append("an implementation reference must record which files were inspected")
    return list(dict.fromkeys(problems))


# ------------------------------------------------------------ dependency safety

def dependency_request(
    *,
    need: str,
    package: str,
    requested_by: str,
    reason: str,
    approved_approval_id: str = "",
) -> dict:
    """A reference's use of a library becomes a *request*, never an install.

    There is no code path here that installs, downloads or resolves anything, and
    that is structural rather than a policy check someone could relax later. The
    returned record says what is needed and what it is waiting for; turning it into
    an install requires the human G2 gate that Ariadne has always used, and the
    component ladder's ``INSTALL_AUTHORITY`` stays ``none`` throughout.
    """
    if not str(package).strip():
        raise ContractError("a dependency request must name the package it would install")
    approved = bool(str(approved_approval_id).strip())
    return {
        "need": str(need),
        "package": str(package),
        "requested_by": str(requested_by),
        "reason": str(reason),
        "status": "APPROVED" if approved else "REFUSED_PENDING_HUMAN_G2",
        "approval_id": str(approved_approval_id),
        "install_authority": "none â€” human G2 required",
        "installed": False,
        "note": (
            "a reference using a library is evidence that the library exists, not authorisation to add "
            "it. The dependency decision belongs to the human gate that already governs every package"
        ),
    }


__all__ = [
    "MAX_COMPONENT_FILES",
    "PRIMITIVE_PATTERNS",
    "SKIP_DIRS",
    "decide_reuse",
    "dependency_request",
    "implementation_reference",
    "inventories",
    "inventory",
    "latest_inventory",
    "record_inventory",
    "reference_problems",
]
