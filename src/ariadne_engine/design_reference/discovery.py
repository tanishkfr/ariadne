"""Project-first design evidence discovery (AR-220).

> **Project identity comes before external inspiration.**

Before any external retrieval, Ariadne looks at the project it is designing for.
This is not politeness. A project's own tokens, stylesheets and component library
are *constraints*, while an external reference is *evidence*, and a design
direction that borrows a palette from a catalog instead of using the project's own
brand tokens has inverted the priority order and produced a direction the project
does not want.

Each probe reports what it found, honestly, including "found nothing". A probe
that cannot find anything records ``UNKNOWN`` rather than guessing, and
:func:`external_reference_worthwhile` refuses to recommend external research while
project-local evidence is still unexamined - which is what stops a run from
reaching for the network before it has looked at the repository it is in.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Mapping, Sequence

from ..contracts import ContractError
from . import safety

DESIGN_DOCUMENTS = ("DESIGN.md", "docs/DESIGN.md", "design/DESIGN.md", "AGENTS.md", "PROJECT.md")
"""Where a project's own design intent is expected to live, in preference order."""

TOKEN_FILES = (
    "tailwind.config.js", "tailwind.config.ts", "tailwind.config.mjs", "tailwind.config.cjs",
    "design-tokens.json", "tokens.json", "design/tokens.json", "styles/tokens.css",
    "theme.css", "src/styles/theme.css", "app/globals.css", "src/app/globals.css",
)
"""Candidate token/style entry points. Probed by name, never by globbing the tree."""

STYLESHEET_NAMES = ("*.css",)
COMPONENT_DIRS = (
    Path("src") / "components", Path("components"), Path("src") / "ui", Path("ui"),
    Path("packages") / "ui" / "src", Path("src") / "lib" / "ui",
)
FIGMA_HINTS = ("figma.com", "figma.link")

CSS_VARIABLE_RE = re.compile(r"--([A-Za-z0-9_-]{1,60})\s*:\s*([^;{}]{1,120})")
_TAILWIND_COLOR_RE = re.compile(r"^\s{2,6}(?P<key>[A-Za-z0-9_-]{1,40}):\s*(?P<value>#[0-9a-fA-F]{3,8})", re.MULTILINE)

MAX_TOKEN_SAMPLES = 80
"""Ceiling on the tokens a discovery record carries.

Enough to characterise a palette; not so many that the run state becomes a copy
of the project's stylesheet. The full stylesheet stays where it is.
"""


def _relative(project: Path, path: Path) -> str:
    try:
        return path.relative_to(project).as_posix()
    except ValueError:  # pragma: no cover - contained by callers
        return path.name


def _bounded(project: Path, relative: str) -> Path | None:
    """Resolve a project-relative probe path, refusing anything outside the tree."""
    try:
        return safety.contained_path(relative, project, label=f"design probe {relative}")
    except ContractError:
        return None


def discover_design_documents(project: Path) -> list[dict]:
    """Locate the project's own design documents."""
    found: list[dict] = []
    for relative in DESIGN_DOCUMENTS:
        path = _bounded(project, relative)
        if path is None or not path.is_file():
            continue
        raw = path.read_bytes()
        size = safety.check_document_size(
            raw, limit=1_048_576, label=f"project design document {relative}"
        )
        found.append({
            "kind": "DESIGN_DOCUMENT",
            "path": _relative(project, path),
            "bytes": size,
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
    return found


def discover_tokens(project: Path) -> dict:
    """Characterise the project's own design tokens.

    Reads declared entry points by name. Reports *counts and named samples*, never
    a full copy: the stylesheet is the project's artefact, and the run only needs
    enough to say what identity the project already has.
    """
    css_variables: dict[str, str] = {}
    tailwind_colours: dict[str, str] = {}
    files: list[str] = []
    for relative in TOKEN_FILES:
        path = _bounded(project, relative)
        if path is None or not path.is_file():
            continue
        files.append(_relative(project, path))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if path.suffix.lower() == ".css":
            for name, value in CSS_VARIABLE_RE.findall(text):
                if len(css_variables) >= MAX_TOKEN_SAMPLES:
                    break
                css_variables[name] = value.strip()
        else:
            for match in _TAILWIND_COLOR_RE.finditer(text):
                if len(tailwind_colours) >= MAX_TOKEN_SAMPLES:
                    break
                tailwind_colours[match.group("key")] = match.group("value")
    return {
        "kind": "DESIGN_TOKENS",
        "files": files,
        "css_variable_count": len(css_variables),
        "css_variable_names": sorted(css_variables)[:MAX_TOKEN_SAMPLES],
        "tailwind_colour_count": len(tailwind_colours),
        "tailwind_colour_keys": sorted(tailwind_colours)[:MAX_TOKEN_SAMPLES],
        "found": bool(css_variables or tailwind_colours),
        "note": (
            "named samples only; the stylesheet remains the project's artefact and is not copied into "
            "run state"
        ),
    }


def discover_component_library(project: Path) -> dict:
    """Report whether the project already has a component library of its own."""
    directories: list[str] = []
    component_count = 0
    for relative in COMPONENT_DIRS:
        path = _bounded(project, relative.as_posix())
        if path is None or not path.is_dir():
            continue
        directories.append(relative.as_posix())
        component_count += sum(1 for item in path.rglob("*") if item.is_file() and item.suffix in (".tsx", ".jsx", ".vue", ".svelte"))
    return {
        "kind": "COMPONENT_LIBRARY",
        "directories": directories,
        "component_files": component_count,
        "found": bool(directories and component_count),
        "note": (
            "a project that already has components has an implementation reference available without any "
            "external retrieval, and that is rung one of the component ladder"
        ),
    }


def discover_figma_links(project: Path) -> dict:
    """Find declared Figma links. Discovery only - no MCP is contacted."""
    urls: list[str] = []
    for relative in DESIGN_DOCUMENTS + ("README.md", "package.json", "docs/README.md"):
        path = _bounded(project, relative)
        if path is None or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for hint in FIGMA_HINTS:
            for match in re.finditer(rf"https?://[^\s\"'<>)]*{re.escape(hint)}[^\s\"'<>)]*", text):
                url = match.group(0).rstrip(".,);")
                if url not in urls:
                    urls.append(url)
    return {
        "kind": "FIGMA_LINK",
        "urls": urls[:20],
        "found": bool(urls),
        "note": (
            "a declared Figma URL is not inspected evidence. Without a configured MCP connection it is "
            "recorded as an opportunity and nothing is claimed about the document behind it"
        ),
    }


def discover(project: Path) -> dict:
    """Run every local probe and return one discovery record."""
    root = Path(project)
    if not root.is_dir():
        raise ContractError(f"design discovery needs a project directory: {root}")
    documents = discover_design_documents(root)
    tokens = discover_tokens(root)
    components = discover_component_library(root)
    figma = discover_figma_links(root)
    # A design document *is* project identity even before it is parsed, so its
    # presence is recorded as an identity source directly. Only the other three
    # probes carry a `found` flag.
    identity = ["DESIGN_DOCUMENT"] if documents else []
    identity += [row["kind"] for row in (tokens, components, figma) if row.get("found")]
    return {
        "project": str(root),
        "probes": {
            "design_documents": documents,
            "design_tokens": tokens,
            "component_library": components,
            "figma_links": figma,
        },
        "identity_established": bool(identity),
        "identity_sources": identity,
        "sufficient_locally": bool(documents) or bool(tokens.get("found")) or bool(components.get("found")),
    }


def external_reference_worthwhile(discovery: Mapping, *, project_sufficient: bool = False) -> dict:
    """Whether external reference research is justified yet.

    Two brakes, both deliberate:

    * **project-first** - if project-local identity has not been examined at all,
      the answer is ``NO`` and the reason names the probes that must run. Looking
      at a catalog before looking at the repository is how a project ends up
      styled like somebody else's brand.
    * **sufficiency** - if the project's own evidence is already sufficient for
      the requested depth, the answer is ``NO``. Reference acquisition is not
      free, and "there is always another reference" is how a research budget stops
      existing.

    It never returns ``YES`` for its own sake: it reports what it examined.
    """
    if not discovery.get("probes"):
        raise ContractError("external reference value cannot be judged without a discovery record")
    if not discovery.get("identity_established") and not project_sufficient:
        return {
            "verdict": "NO",
            "reason": (
                "project-local design evidence has not been examined; run the local probes first, "
                "because the project's own identity constrains the design before any reference informs it"
            ),
        }
    if discovery.get("sufficient_locally") and not project_sufficient:
        return {
            "verdict": "NO",
            "reason": (
                "the project already establishes design evidence of its own; external references would "
                "supplement that identity, and supplementing is optional rather than automatic"
            ),
            "identity_sources": list(discovery.get("identity_sources") or []),
        }
    return {
        "verdict": "YES",
        "reason": "project-local evidence is present but the stated requirement reaches beyond it",
        "identity_sources": list(discovery.get("identity_sources") or []),
        "constraints": [
            "project tokens constrain colour and type; a reference palette does not override them",
            "a project component library is the first implementation reference, ahead of any registry",
        ],
    }


def local_reference_records(discovery: Mapping, *, project: Path) -> list[dict]:
    """Turn a discovery record into candidate local reference payloads.

    Only documents are returned as *reference candidates*. Token counts and
    component-directory listings are project constraints, not references: a
    stylesheet that happens to define variables is not a design reference someone
    inspected, and recording it as one would inflate the reference set with the
    project itself.
    """
    rows: list[dict] = []
    for row in (discovery.get("probes") or {}).get("design_documents") or []:
        if not isinstance(row, Mapping) or row.get("kind") != "DESIGN_DOCUMENT":
            continue
        relative = str(row.get("path", ""))
        path = _bounded(project, relative)
        if path is None or not path.is_file():
            continue
        rows.append({
            "reference_type": "LOCAL_DESIGN_FILE",
            "title": path.name,
            "locator": str(path),
            "relative_path": relative,
            "bytes": int(row.get("bytes", 0) or 0),
            "sha256": str(row.get("sha256", "")),
            "source_kind": "LOCAL_DESIGN_FILE",
            "note": "the project's own design document",
        })
    return rows


def summarise(discovery: Mapping) -> str:
    """A short human view of what the project already establishes."""
    lines = ["Project-local design evidence"]
    probes = discovery.get("probes") if isinstance(discovery.get("probes"), Mapping) else {}
    documents = probes.get("design_documents") or []
    lines.append(f"  design documents: {len(documents)}" + (
        " (" + ", ".join(str(row.get("path")) for row in documents) + ")" if documents else ""
    ))
    tokens = probes.get("design_tokens") if isinstance(probes.get("design_tokens"), Mapping) else {}
    lines.append(
        f"  design tokens:    {tokens.get('css_variable_count', 0)} CSS variables, "
        f"{tokens.get('tailwind_colour_count', 0)} Tailwind colours"
    )
    components = probes.get("component_library") if isinstance(probes.get("component_library"), Mapping) else {}
    lines.append(f"  component library: {components.get('component_files', 0)} component files")
    figma = probes.get("figma_links") if isinstance(probes.get("figma_links"), Mapping) else {}
    lines.append(f"  declared Figma links: {len(figma.get('urls') or [])}")
    return "\n".join(lines)


__all__ = [
    "COMPONENT_DIRS",
    "DESIGN_DOCUMENTS",
    "MAX_TOKEN_SAMPLES",
    "TOKEN_FILES",
    "discover",
    "discover_component_library",
    "discover_design_documents",
    "discover_figma_links",
    "discover_tokens",
    "external_reference_worthwhile",
    "local_reference_records",
    "summarise",
]