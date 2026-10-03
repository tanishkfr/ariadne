"""DESIGN.md as an *input format*, parsed by an adapter (AR-220).

DESIGN.md is a third-party interchange format - Google Stitch's specification
plus a widely used nine-section extension. It is **not** Ariadne's canonical
schema, and this module never lets it become one. The shape of the pipeline is:

```
DESIGN.md â”€â”€â–¶ parse_design_md â”€â”€â–¶ raw token/rationale blocks â”€â”€â–¶ DesignReference
```

The parser is deliberately small and deliberately strict:

* **No third-party dependency.** Ariadne core is standard-library only, so this
  is a bounded subset parser, not a general YAML implementation. It handles the
  constructs the real corpus actually uses: nested mappings, block lists, inline
  ``[a, b]`` lists, quoted and bare scalars, and ``{token.path}`` references.
* **Duplicate keys are refused.** A design document that defines ``primary``
  twice has two values and one meaning; silently keeping the last one would make
  the parsed record disagree with the bytes while both claim the same digest.
* **Oversized input is refused**, not truncated.
* **Unknown keys are preserved.** A field Ariadne does not understand is
  recorded under ``unknown_fields`` with a warning, never discarded: the
  rationale in a design document is the part that carries the thinking.
* **Structurally dangerous input is refused**: tab indentation, unbalanced
  quotes/brackets, anchors, aliases, tags, and nesting deeper than the bound.
* **Content is data.** Nothing parsed here can execute, resolve a filesystem
  path, or grant a permission. A design document that instructs the reader to
  install a package produces a parsed ``injection_scan`` finding and nothing
  else.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from .. import contracts
from ..contracts import ContractError
from . import safety

FRONTMATTER_FENCE = "---"
"""The YAML frontmatter delimiter DESIGN.md uses."""

MAX_NESTING_DEPTH = 12
"""Bound on mapping/list nesting. A design document has no legitimate reason to
exceed this, and unbounded recursion on attacker-supplied input is how a parser
becomes a denial of service."""

_MAX_KEY = 200
_MAX_TOKEN_REFERENCE_DEPTH = 6

_KEY_RE = re.compile(r"^(?P<key>[\w.\-]+|\"[^\"]*\"|'[^']*')\s*:(?:\s+(?P<value>.*))?$")
_ITEM_RE = re.compile(r"^-\s+(?P<value>.*)$")
_TOKEN_REF_RE = re.compile(r"^\{([\w.\-]+)\}$")
"""A plain mapping key.

``\\w`` is Unicode-aware in Python, so a non-ASCII key is a key. The real corpus
contains at least one ``属于:`` ("belongs to") field, and refusing it would have
meant refusing a published design document over a field name. An unrecognised
key is preserved under ``unknown_fields`` and warned about, which is the
behaviour the format promises; only structurally *dangerous* input is refused.
"""

UNSAFE_CONSTRUCTS = (
    ("anchor", re.compile(r"(?:^|[\s:\-])&[A-Za-z_][A-Za-z0-9_-]*")),
    ("alias", re.compile(r"(?:^|[\s:\[,\-])\*[A-Za-z_][A-Za-z0-9_-]*(?![\w*])")),
    ("tag", re.compile(r"(?:^|[\s:\-])!(?:yaml|!!?[A-Za-z_][\w/.-]*)")),
    ("directive", re.compile(r"(?m)^[ \t]*%\w")),
)
"""YAML constructs a design document has no business using.

Anchors and aliases are expansion gadgets: ``*base`` can turn one short line into
an unbounded graph walk. Tags can select a constructor. Directives mutate global
parser state. A design system document needs none of them, so all three are
refused by name rather than handled.

The patterns are scoped to YAML *token positions* - line start, or immediately
after ``:``, ``-``, ``[``, ``,`` or whitespace inside a value - and are applied
only to the frontmatter block. Applying them to the whole document would refuse
ordinary markdown emphasis (``**Linear**``) and italic prose in a rationale
section, which is exactly the "silently discard useful design rationale" failure
this module exists to avoid.
"""

BOM = chr(0xFEFF)
"""The UTF-8 byte-order mark, written as an explicit code point.

A ``DESIGN.md`` committed with a BOM opens with ``\ufeff---`` rather than ``---``, and a
parser that does not strip it concludes the document has no frontmatter and silently reports
zero tokens while still recording a digest of the file.
"""

DOCUMENT_SECTIONS = (
    "overview", "colors", "typography", "layout", "elevation-depth",
    "shapes", "components", "dos-and-donts", "responsive-behavior",
)
"""The nine-section contract the published corpus follows, in order.

The slugs are exactly what :func:`slugify_heading` produces for the corpus
headings - including ``dos-and-donts``, which is how ``## Do's and Don'ts``
slugifies. A vocabulary that drifted from the slugifier would report every
document as missing its do/don't section, which is a false negative about the
one section most likely to carry anti-pattern guidance.

Recorded as a *recognised vocabulary*, not a validation requirement: a project
DESIGN.md is not required to have nine sections, and its absence is noted rather
than refused. What is recorded is which sections were present, so a direction
can honestly say what it was and was not given."""

_FRONT_MATTER_KEYS = (
    "version", "name", "description", "colors", "typography", "rounded",
    "spacing", "components", "layout", "motion", "imagery", "elevation",
    "borders", "states", "grid", "tokens", "usage", "license", "source",
)


# ------------------------------------------------------------------- scalars


def _scalar(raw: str) -> Any:
    text = raw.strip()
    if not text:
        return None
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        inner = text[1:-1]
        if text[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
        return inner
    if text.startswith("[") and text.endswith("]"):
        body = text[1:-1].strip()
        if not body:
            return []
        return [_scalar(part) for part in _split_inline(body)]
    lowered = text.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if lowered in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d*\.\d+", text):
        return float(text)
    return text


def _split_inline(body: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    quote = ""
    current: list[str] = []
    for char in body:
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
            continue
        if char in "\"'":
            quote = char
            current.append(char)
            continue
        if char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]


# ------------------------------------------------------------- subset parsing


class _DuplicateKey(ContractError):
    """A mapping defined the same key twice."""


def parse_yaml_subset(text: str) -> dict:
    """Parse the bounded YAML subset DESIGN.md frontmatter uses.

    Only mappings and block/inline lists of scalars are produced. Anything the
    subset cannot represent faithfully is refused by name instead of being
    approximated, because a half-parsed token table that still carries a digest
    is worse than no record at all.
    """
    lines: list[tuple[int, int, str]] = []
    for number, raw in enumerate(str(text or "").splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ContractError(
                f"frontmatter line {number} is indented with a tab; YAML forbids tab indentation and "
                "a design document may not smuggle ambiguous structure past the parser"
            )
        indent = len(raw) - len(raw.lstrip())
        lines.append((indent, number, raw.strip()))
    value, index = _parse_block(lines, 0, indent_of=lines[0][0] if lines else 0, depth=0)
    if index != len(lines):
        raise ContractError(f"frontmatter line {lines[index][1]} could not be parsed as part of this structure")
    if not isinstance(value, dict):
        raise ContractError("DESIGN.md frontmatter must be a mapping at the top level")
    return value


def indent_of(lines: list[tuple[int, int, str]]) -> int:  # pragma: no cover - trivial
    return lines[0][0] if lines else 0


def _parse_block(lines: list[tuple[int, int, str]], index: int, *, indent_of: int, depth: int) -> tuple[Any, int]:
    if depth > MAX_NESTING_DEPTH:
        raise ContractError(
            f"frontmatter nests deeper than {MAX_NESTING_DEPTH} levels; the document is refused rather "
            "than parsed partially"
        )
    if index >= len(lines):
        return {}, index
    if _ITEM_RE.match(lines[index][2]):
        return _parse_list(lines, index, indent=lines[index][0], depth=depth)
    return _parse_mapping(lines, index, indent=lines[index][0], depth=depth)


def _parse_mapping(lines, index: int, *, indent: int, depth: int) -> tuple[dict, int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        current_indent, number, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ContractError(f"frontmatter line {number} is indented deeper than its parent without a key")
        match = _KEY_RE.match(content)
        if not match:
            raise ContractError(f"frontmatter line {number} is not a mapping entry: {content!r}")
        raw_key = match.group("key")
        key = raw_key[1:-1] if raw_key[0] in "\"'" else raw_key
        if key in result:
            raise _DuplicateKey(
                f"frontmatter line {number} defines {key!r} a second time; a design document that "
                "declares the same token twice has two values and one meaning, so it is refused"
            )
        inline = match.group("value")
        index += 1
        block_scalar = _BLOCK_SCALAR_RE.match(inline or "")
        if block_scalar is not None:
            # `|` and `>` literal/folded block scalars. The published corpus puts
            # every long rationale in one of these, so a parser that cannot read
            # them sees no description at all on most documents. The parser
            # returns the next index, which must be carried out of here or the
            # loop re-reads the scalar's own body as structure.
            result[key], index = _parse_block_scalar(
                lines, index, indent=current_indent, style=block_scalar.group(1)
            )
            continue
        if inline is not None and inline.strip():
            result[key] = _scalar(inline)
            continue
        if index < len(lines) and lines[index][0] > current_indent:
            child, index = _parse_block(lines, index, indent_of=lines[index][0], depth=depth + 1)
            result[key] = child
            continue
        result[key] = None
    return result, index


_BLOCK_SCALAR_RE = re.compile(r"^(?P<style>[|>])(?P<chomp>[+-]?)(?P<indent>\d*)$")


def _parse_block_scalar(lines, index: int, *, indent: int, style: str) -> tuple[str, int]:
    """Read a ``|``/``>`` block scalar, returning its text and the next index.

    Every line indented deeper than the owning key belongs to the scalar, whatever
    it looks like. That is what the format means, and trying to interpret the
    content as structure is how a rationale paragraph becomes a parse error.
    """
    collected: list[str] = []
    while index < len(lines):
        current_indent, _number, content = lines[index]
        if current_indent <= indent:
            break
        collected.append(" " * (current_indent - indent - 2 if current_indent - indent - 2 > 0 else 0) + content)
        index += 1
    if style == ">":
        text = " ".join(collected)
    else:
        text = "\n".join(collected)
    return text.strip(), index


def _parse_list(lines, index: int, *, indent: int, depth: int) -> tuple[list, int]:
    result: list[Any] = []
    while index < len(lines):
        current_indent, number, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ContractError(f"frontmatter line {number} is over-indented inside a list")
        match = _ITEM_RE.match(content)
        if not match:
            break
        body = match.group("value").strip()
        index += 1
        if _KEY_RE.match(body) and not body.startswith("{"):
            nested_key = _KEY_RE.match(body).group("key")  # type: ignore[union-attr]
            block: dict[str, Any] = {}
            inline = _KEY_RE.match(body).group("value")  # type: ignore[union-attr]
            if inline and inline.strip():
                block[nested_key] = _scalar(inline)
            elif index < len(lines) and lines[index][0] > current_indent:
                child, index = _parse_block(lines, index, indent_of=lines[index][0], depth=depth + 1)
                block = child if isinstance(child, dict) else {nested_key: child}
            else:
                block[nested_key] = None
            result.append(block)
            continue
        result.append(_scalar(body))
    return result, index


# --------------------------------------------------------------- frontmatter


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split ``---`` frontmatter from the rationale body.

    Returns ``("", text)`` when there is no frontmatter at all. A document with
    no frontmatter is still a legitimate design document - it is simply a
    rationale with no machine-readable token block, and that is recorded rather
    than refused.
    """
    body = str(text or "")
    stripped = body.lstrip(BOM).lstrip()
    if not stripped.lstrip().startswith(FRONTMATTER_FENCE):
        return "", body
    lines = stripped.splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == FRONTMATTER_FENCE)
    for index in range(start + 1, len(lines)):
        if lines[index].strip() == FRONTMATTER_FENCE:
            return "\n".join(lines[start + 1:index]), "\n".join(lines[index + 1:])
    raise ContractError(
        "DESIGN.md frontmatter opens with '---' but is never closed; the document is refused rather "
        "than parsed as an unterminated block"
    )


def read_design_md(path: Path, *, project: Path | None = None, label: str = "DESIGN.md") -> dict:
    """Read and parse one design document from disk, under the size bound."""
    target = safety.contained_path(path, project, label=label) if project is not None else Path(path)
    if not target.is_file():
        raise ContractError(f"{label} does not exist: {target}")
    raw = target.read_bytes()
    safety.check_document_size(
        raw, limit=contracts.MAX_DESIGN_REFERENCE_BYTES, label=f"{label} ({target.name})"
    )
    return parse_design_md(raw.decode("utf-8", errors="replace"), origin=str(target))


def parse_design_md(text: str, *, origin: str = "") -> dict:
    """Parse a DESIGN.md into ``{frontmatter, body, tokens, sections, ...}``.

    The returned dict is the *raw* parsed form. Turning it into an Ariadne
    ``DesignReference`` is :mod:`ariadne_engine.design_reference.normalize`'s
    job, and keeping the two apart is what stops a third-party interchange
    format from becoming Ariadne's internal schema.
    """
    if not isinstance(text, str):
        raise ContractError("a DESIGN.md must be supplied as text")
    safety.check_document_size(
        text, limit=contracts.MAX_DESIGN_REFERENCE_BYTES, label="DESIGN.md document"
    )
    frontmatter_text, body = split_frontmatter(text)
    for label, pattern in UNSAFE_CONSTRUCTS:
        match = pattern.search(frontmatter_text)
        if match:
            raise ContractError(
                f"DESIGN.md frontmatter uses the {label} construct {match.group(0).strip()!r}; anchors, "
                "aliases, tags and directives are expansion or state gadgets with no place in a design "
                "document's machine-readable block"
            )
    frontmatter: dict[str, Any] = {}
    warnings: list[str] = []
    if frontmatter_text.strip():
        try:
            frontmatter = parse_yaml_subset(frontmatter_text)
        except _DuplicateKey as exc:
            raise ContractError(str(exc)) from exc
    unknown = sorted(
        key for key in frontmatter if key not in _FRONT_MATTER_KEYS
    )
    if unknown:
        warnings.append(
            "unrecognised frontmatter fields preserved rather than discarded: " + ", ".join(unknown)
        )
    sections = extract_sections(body)
    safety.check_count(
        len(sections), limit=contracts.MAX_DESIGN_REFERENCE_SECTIONS, label="DESIGN.md section count"
    )
    return {
        "origin": str(origin),
        "frontmatter": frontmatter,
        "body": body,
        "sections": sections,
        "section_names": sorted(sections),
        "declared_version": str(frontmatter.get("version", "") or ""),
        "declared_name": str(frontmatter.get("name", "") or ""),
        "declared_description": str(frontmatter.get("description", "") or ""),
        "tokens": extract_tokens(frontmatter),
        "token_references": extract_token_references(frontmatter),
        "unknown_fields": {key: frontmatter[key] for key in unknown},
        "missing_sections": [name for name in DOCUMENT_SECTIONS if name not in sections],
        "warnings": warnings,
        "injection_scan": safety.scan_reference_text(text),
    }


def extract_sections(body: str) -> dict[str, list[str]]:
    """Markdown sections keyed by a slug of their heading.

    Headings are matched on their text, not on a CSS or DOM selector, so a
    markdown document is parsed by its own structure.
    """
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in str(body or "").splitlines():
        heading = re.match(r"^(#{1,6})\s+(.*\S)\s*$", raw)
        if heading:
            current = slugify_heading(heading.group(2))
            sections.setdefault(current, [])
            continue
        if current and raw.strip():
            sections[current].append(raw.strip())
    return sections


def slugify_heading(text: str) -> str:
    value = re.sub(r"[^\w\s-]", "", str(text).strip().lower())
    return re.sub(r"[\s_-]+", "-", value).strip("-")


def extract_tokens(frontmatter: Mapping[str, Any]) -> dict:
    """The machine-readable token blocks, kept separate from the rationale.

    Token *groups* are recognised rather than token *values* invented: an absent
    group is absent, and a value is carried through verbatim so no token is
    synthesised from prose.
    """
    groups = {
        "colors": frontmatter.get("colors"),
        "typography": frontmatter.get("typography"),
        "rounded": frontmatter.get("rounded"),
        "spacing": frontmatter.get("spacing"),
        "components": frontmatter.get("components"),
    }
    for extra in ("layout", "motion", "imagery", "elevation", "borders", "states", "grid", "tokens"):
        if frontmatter.get(extra) is not None:
            groups[extra] = frontmatter[extra]
    return {
        name: _flatten_group(value)
        for name, value in groups.items()
        if isinstance(value, Mapping)
    }


def _flatten_group(value: Mapping[str, Any]) -> list[dict]:
    rows: list[dict] = []
    safety.check_count(
        len(value), limit=contracts.MAX_DESIGN_REFERENCE_PATTERNS,
        label=f"DESIGN.md token group of {len(value)} entries",
    )
    for name in sorted(value):
        entry = value[name]
        row: dict[str, Any] = {"name": str(name)}
        if isinstance(entry, Mapping):
            row["values"] = {str(k): entry[k] for k in sorted(entry)}
        else:
            row["values"] = {"value": entry}
        rows.append(row)
    return rows


def extract_token_references(frontmatter: Mapping[str, Any]) -> list[dict]:
    """Every ``{group.name}`` reference, with its referent resolved if present.

    Resolution is by *name only*, with a depth bound. It never touches the
    filesystem, never performs an interpolation into an expression, and never
    raises on a dangling reference - a dangling reference is recorded as
    unresolved, because a design document may legitimately name a token it does
    not define.
    """
    found: list[dict] = []

    def walk(node: Any, path: tuple[str, ...], depth: int) -> None:
        if depth > _MAX_TOKEN_REFERENCE_DEPTH:
            return
        if isinstance(node, Mapping):
            for key in sorted(node, key=str):
                walk(node[key], path + (str(key),), depth + 1)
            return
        if isinstance(node, list):
            for item in node:
                walk(item, path, depth + 1)
            return
        if not isinstance(node, str):
            return
        match = _TOKEN_REF_RE.match(node.strip())
        if not match:
            return
        target = match.group(1)
        parts = target.split(".")
        group = parts[0] if parts else ""
        name = ".".join(parts[1:]) if len(parts) > 1 else ""
        found.append({
            "reference": target,
            "referenced_at": ".".join(path),
            "group": group,
            "name": name,
            "resolved": group in frontmatter and name in (frontmatter.get(group) or {}),
        })

    walk(frontmatter, (), 0)
    return found


def validation_problems(parsed: Mapping[str, Any]) -> list[str]:
    """Deterministic validation of the subset Ariadne consumes.

    Problems are *structural*: a structurally dangerous document is refused,
    while an incomplete one is merely reported. Useful design reasoning that
    Ariadne does not model must not be thrown away.
    """
    problems: list[str] = []
    frontmatter = parsed.get("frontmatter") if isinstance(parsed.get("frontmatter"), Mapping) else {}
    if not frontmatter:
        problems.append("the document declares no machine-readable frontmatter")
    else:
        if not str(frontmatter.get("name", "") or "").strip():
            problems.append("frontmatter declares no name, so the document has no stable identity")
        tokens = parsed.get("tokens") if isinstance(parsed.get("tokens"), Mapping) else {}
        if not tokens:
            problems.append("frontmatter declares no recognised token group")
        unresolved = [
            item for item in (parsed.get("token_references") or [])
            if isinstance(item, Mapping) and not item.get("resolved")
        ]
        if unresolved:
            problems.append(
                f"{len(unresolved)} token reference(s) name a token the document does not define"
            )
    sections = parsed.get("sections") if isinstance(parsed.get("sections"), Mapping) else {}
    if not sections:
        problems.append("the document has no rationale sections, so it records no reasoning")
    version = str(parsed.get("declared_version", "") or "")
    if version and not re.fullmatch(r"[A-Za-z0-9._\-]{1,32}", version):
        problems.append(f"frontmatter declares an unusable version string: {version!r}")
    return list(dict.fromkeys(problems))


def summarise(parsed: Mapping[str, Any]) -> dict:
    """A compact, honest description of what was parsed."""
    tokens = parsed.get("tokens") if isinstance(parsed.get("tokens"), Mapping) else {}
    return {
        "name": str(parsed.get("declared_name", "") or ""),
        "version": str(parsed.get("declared_version", "") or ""),
        "token_groups": {name: len(rows) for name, rows in sorted(tokens.items())},
        "sections": list(parsed.get("section_names") or []),
        "missing_sections": list(parsed.get("missing_sections") or []),
        "unknown_fields": sorted(parsed.get("unknown_fields") or {}),
        "warnings": list(parsed.get("warnings") or []),
        "validation_problems": validation_problems(parsed),
        "instruction_attempts": len(
            (parsed.get("injection_scan") or {}).get("instruction_attempts") or []
        ),
    }


__all__ = [
    "DOCUMENT_SECTIONS",
    "MAX_NESTING_DEPTH",
    "UNSAFE_CONSTRUCTS",
    "extract_sections",
    "extract_token_references",
    "extract_tokens",
    "parse_design_md",
    "parse_yaml_subset",
    "read_design_md",
    "slugify_heading",
    "split_frontmatter",
    "summarise",
    "validation_problems",
]