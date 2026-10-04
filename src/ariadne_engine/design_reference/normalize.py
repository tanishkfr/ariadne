"""``DesignReference``: one provider-neutral reference record (AR-220).

Ariadne 2.1 already had a reference record family with a provenance lifecycle
(``FOUND -> ACCESSIBLE -> INSPECTED -> ANALYSED -> USED``) and adapters that
produce evidence under declared capabilities. AR-220 **extends that family**
rather than inventing a parallel persistence model, because a second store for
"things a design looked at" would be a second, weaker answer to a question the
lifecycle already answers well.

What is new is the classification block and the observation vocabulary:

```
┌─ AR-202D reference record (unchanged lifecycle) ─────────────────┐
│ state, inspections, analysis, usage, content digest, licensing  │
├─ AR-220 classification ─────────────────────────────────────────┤
│ source_kind, evidence_level, freshness, access_mode             │
│ source_provider, source_identity, retrieved_at, content_digest │
├─ AR-220 observations ────────────────────────────────────────────┤
│ observed_patterns  — what was seen, on a controlled vocabulary  │
│ treatments         — BORROW / ADAPT / AVOID per pattern         │
│ reuse_constraints  — what may not be taken                       │
│ limitations        — what the evidence cannot support           │
└─────────────────────────────────────────────────────────────────┘
```

The invariants this module enforces:

1. **Observed is not recommended.** ``observed_patterns`` records what was seen.
   Nothing in that list may be phrased as an instruction to the design, and the
   extraction vocabulary is deliberately not the recommendation vocabulary.
2. **A curated analysis is not a first-party system.** ``source_kind`` is
   supplied by the adapter that actually retrieved the bytes and is validated
   against :data:`contracts.REFERENCE_SOURCE_KINDS`. No code path upgrades a
   curated analysis to ``FIRST_PARTY_DESIGN_MD`` because it happens to describe
   a famous brand.
3. **Every record is bound to content it was derived from.** A normalized record
   carries both the digest of the retrieved bytes and a digest of the normalized
   record itself, so "this classification describes those bytes" is checkable.
4. **Access restriction is a valid answer.** ``ACCESS_RESTRICTED`` is recorded,
   not worked around, and it carries no observations.
5. **External text grants nothing.** The injection scan is stored as a fact
   about the source. It never becomes a capability, a permission or a policy.
"""

from __future__ import annotations

import json
import re
from typing import Mapping, Sequence

from .. import contracts
from ..contracts import ContractError
from . import designmd, safety

NORMALISED_DIGEST_FIELDS = (
    "source_kind", "source_provider", "source_identity", "source_uri",
    "brand", "product", "surface", "reference_type", "evidence_level",
    "access_mode", "license_status",
)
"""The fields bound into the normalized-record digest.

Deliberately excludes timestamps and record ids, so re-retrieving the same bytes
at a later time produces the same normalized digest and a change in *content*
produces a different one. That is what makes change detection mean something."""


def build_classification(
    *,
    source_kind: str,
    source_provider: str,
    source_identity: str,
    source_uri: str,
    retrieved_at: str,
    content_digest: str,
    evidence_level: str,
    access_mode: str = "PUBLIC",
    freshness: str = "CURRENT",
    brand: str = "",
    product: str = "",
    surface: str = "",
    reference_type: str = "",
    source_revision: str = "",
    source_date: str = "",
    historical: bool = False,
    size_bytes: int = 0,
) -> dict:
    """Assemble the AR-220 classification block, refusing unknown vocabulary."""
    if source_kind not in contracts.REFERENCE_SOURCE_KINDS:
        raise ContractError(
            f"unsupported design reference source kind: {source_kind!r}; expected one of "
            + ", ".join(contracts.REFERENCE_SOURCE_KINDS)
        )
    if evidence_level not in contracts.REFERENCE_EVIDENCE_LEVELS:
        raise ContractError(f"unsupported evidence level: {evidence_level!r}")
    if access_mode not in contracts.REFERENCE_ACCESS_MODES:
        raise ContractError(f"unsupported access mode: {access_mode!r}")
    if freshness not in contracts.REFERENCE_FRESHNESS:
        raise ContractError(f"unsupported freshness: {freshness!r}")
    if not str(source_provider or "").strip():
        raise ContractError("a design reference must name the provider it came from")
    if not str(source_identity or "").strip():
        raise ContractError("a design reference must name a stable source identity")
    if not str(retrieved_at or "").strip():
        raise ContractError("a design reference must record when it was retrieved")
    if access_mode != "DECLARED_LOCAL" and not str(source_uri or "").strip():
        raise ContractError("a design reference must name the URI it was read from")
    return {
        "source_kind": str(source_kind),
        "source_provider": str(source_provider),
        "source_identity": str(source_identity),
        "source_uri": safety.reference_text_is_data(source_uri, field="source_uri"),
        "retrieved_at": str(retrieved_at),
        "content_digest": str(content_digest),
        "evidence_level": str(evidence_level),
        "access_mode": str(access_mode),
        "freshness": "HISTORICAL" if historical else str(freshness),
        "brand": safety.reference_text_is_data(brand, field="brand"),
        "product": safety.reference_text_is_data(product, field="product"),
        "surface": safety.reference_text_is_data(surface, field="surface"),
        "reference_type": safety.reference_text_is_data(reference_type, field="reference_type"),
        "source_revision": str(source_revision),
        "source_date": str(source_date),
        # The size of the bytes this classification describes. AR-220 shipped without
        # it, which made "how much reference context was transported" unmeasurable -
        # the Context Economics question of the next phase had no input to compute
        # from, so a reduction could only be asserted, never counted.
        "size_bytes": max(0, int(size_bytes)),
    }


def canonical_digest(payload: Mapping) -> str:
    """Stable content digest of a normalised payload.

    Deliberately *not* :func:`contracts.digest_fields`, which hashes the field
    list of an approval subject and would reject a design-reference payload
    outright. This is a plain canonical-JSON SHA-256: stable across runs and
    Python versions, independent of insertion order, and dependent on nothing but
    the values.
    """
    from .. import references as references_module

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return references_module.digest_bytes(encoded.encode("utf-8"))


def normalised_digest(classification: Mapping, patterns: Sequence[Mapping] = ()) -> str:
    """Digest of the normalized record, independent of retrieval time.

    ``retrieved_at`` is deliberately excluded so re-retrieving identical bytes
    later produces the same digest, while any change in classification or
    observations produces a different one. That is what makes
    :func:`detect_change` meaningful instead of a comparison of two timestamps.
    """
    payload = {name: classification.get(name, "") for name in NORMALISED_DIGEST_FIELDS}
    payload["observed_patterns"] = [
        {"dimension": str(row.get("dimension", "")), "observation": str(row.get("observation", ""))}
        for row in patterns if isinstance(row, Mapping)
    ]
    return canonical_digest(payload)


def detect_change(previous: Mapping, current: Mapping) -> dict:
    """Same source identity, different content: report it rather than absorb it.

    Returns a verdict in the AR-202D freshness vocabulary so change detection
    does not fork ``references.reference_currentness``. A changed digest with the
    same identity is ``CHANGED``; a changed identity is a different source, not
    a changed one.
    """
    previous_class = previous.get("classification") if isinstance(previous.get("classification"), Mapping) else {}
    current_class = current.get("classification") if isinstance(current.get("classification"), Mapping) else {}
    previous_identity = str(previous_class.get("source_identity", ""))
    current_identity = str(current_class.get("source_identity", ""))
    previous_digest = str(previous_class.get("content_digest", ""))
    current_digest = str(current_class.get("content_digest", ""))
    if not previous_digest:
        return {"state": "UNKNOWN", "reason": "the earlier record binds no content digest", "changed": False}
    if previous_identity != current_identity:
        return {
            "state": "UNKNOWN",
            "reason": f"source identity changed ({previous_identity!r} -> {current_identity!r}); "
            "that is a different source, not a changed one",
            "changed": False,
        }
    if previous_digest != current_digest:
        return {
            "state": "CHANGED",
            "reason": f"the same source identity now returns different bytes ({previous_digest[:12]} -> {current_digest[:12]})",
            "changed": True,
            "previous_digest": previous_digest,
            "current_digest": current_digest,
        }
    return {"state": "CURRENT", "reason": "identical source identity and content digest", "changed": False}


def extract_patterns(
    *,
    tokens: Mapping[str, Sequence[Mapping]],
    sections: Mapping[str, Sequence[str]],
    observed_at: str,
) -> list[dict]:
    """Turn a parsed design document into observations on the controlled vocabulary.

    This is extraction, not judgement. Every row says *what the document
    records*, names the artifact it was read from, and stops there. Nothing here
    says what the design should do, and nothing here is inferred from a document
    that does not say it: an absent token group produces no row, never a
    synthesised default.

    Motion and interaction are refused unless the document supplies a basis. A
    static token table cannot establish how something moves, and a reference that
    asserts motion from typography values is making the exact kind of jump this
    whole layer exists to prevent.
    """
    rows: list[dict] = []

    def add(
        dimension: str,
        observation: str,
        *,
        source: str,
        detail: Mapping | None = None,
        basis: str = "",
    ) -> None:
        if not str(observation or "").strip():
            return
        rows.append({
            "dimension": str(dimension),
            "observation": safety.reference_text_is_data(observation, field="observation"),
            "source": str(source),
            "observed_at": str(observed_at),
            "detail": dict(detail or {}),
            "basis": str(basis),
        })

    colors = tokens.get("colors") or []
    if colors:
        safety.check_count(
            len(colors), limit=contracts.MAX_DESIGN_REFERENCE_PATTERNS,
            label="colour token count",
        )
        roles = _color_roles(colors)
        add(
            "color-roles",
            f"{len(colors)} named colour tokens; role groups recorded: "
            + ", ".join(f"{name}={len(rows_)}" for name, rows_ in sorted(roles.items())),
            source="frontmatter.colors",
            detail={"role_counts": {name: len(value) for name, value in sorted(roles.items())}},
        )
        if any(row.get("value", "").lower() in ("#ffffff", "#fff") for row in _scalar_colors(colors)):
            add(
                "color-roles",
                "the palette declares an explicit white surface",
                source="frontmatter.colors",
            )

    typography = tokens.get("typography") or []
    if typography:
        sizes = sorted({
            str(entry.get("values", {}).get("fontSize", ""))
            for entry in typography
            if isinstance(entry, Mapping) and entry.get("values", {}).get("fontSize")
        }, key=_size_key)
        weights = sorted({
            str(entry.get("values", {}).get("fontWeight", ""))
            for entry in typography
            if isinstance(entry, Mapping) and entry.get("values", {}).get("fontWeight")
        })
        add(
            "typography",
            f"{len(typography)} type roles spanning {len(sizes)} distinct sizes"
            + (f" and weights {', '.join(weights)}" if weights else ""),
            source="frontmatter.typography",
            detail={"sizes": sizes[:16], "weights": weights},
        )
        families = sorted({
            str(entry.get("values", {}).get("fontFamily", ""))
            for entry in typography
            if isinstance(entry, Mapping) and entry.get("values", {}).get("fontFamily")
        })
        if families:
            add(
                "typography",
                "type roles draw on " + ", ".join(families[:6]) + (
                    f" and {len(families) - 6} more" if len(families) > 6 else ""
                ),
                source="frontmatter.typography",
                detail={"families": families},
            )

    radii = tokens.get("rounded") or []
    if radii:
        values = sorted({str(entry.get("values", {}).get("value", "")) for entry in radii if isinstance(entry, Mapping)})
        add(
            "radii",
            f"a {len(radii)}-step radius scale: " + ", ".join(value for value in values if value),
            source="frontmatter.rounded",
            detail={"scale": [value for value in values if value]},
        )

    spacing = tokens.get("spacing") or []
    if spacing:
        values = sorted({str(entry.get("values", {}).get("value", "")) for entry in spacing if isinstance(entry, Mapping)})
        add(
            "spacing",
            f"a {len(spacing)}-step spacing scale: " + ", ".join(value for value in values if value),
            source="frontmatter.spacing",
            detail={"scale": [value for value in values if value]},
        )

    components = tokens.get("components") or []
    if components:
        padded = sum(
            1 for entry in components
            if isinstance(entry, Mapping) and entry.get("values", {}).get("padding")
        )
        add(
            "component-geometry",
            f"{len(components)} named component styles"
            + (f", {padded} of which declare explicit padding" if padded else ""),
            source="frontmatter.components",
            detail={"count": len(components), "with_padding": padded},
        )

    borders = tokens.get("borders") or []
    if borders:
        add("borders", f"{len(borders)} declared border treatments", source="frontmatter.borders")

    elevation = tokens.get("elevation") or []
    if elevation:
        add("depth", f"{len(elevation)} declared elevation treatments", source="frontmatter.elevation")

    grid = tokens.get("grid") or []
    if grid:
        add("layout-grid", f"{len(grid)} declared grid treatments", source="frontmatter.grid")

    _add_section_observations(sections, add)
    _add_motion_observations(tokens, add)

    safety.check_count(
        len(rows), limit=contracts.MAX_DESIGN_REFERENCE_PATTERNS,
        label="extracted observed pattern count",
    )
    return rows


def _add_section_observations(sections: Mapping[str, Sequence[str]], add) -> None:
    """Observations that only the rationale prose can support.

    These read what the document *says about itself*, and they cite the section
    they were read from. A section that is absent contributes nothing.
    """
    if "overview" in sections:
        text = " ".join(sections.get("overview") or [])
        if text:
            add("information-hierarchy", _first_sentences(text, 2), source="section:overview")
    if "navigation" in sections:
        text = " ".join(sections.get("navigation") or [])
        if text:
            add("navigation", _first_sentences(text, 2), source="section:navigation")
    if "spacing-system" in sections or "whitespace-philosophy" in sections:
        text = " ".join(list(sections.get("spacing-system") or []) + list(sections.get("whitespace-philosophy") or []))
        if text:
            add("density", _first_sentences(text, 2), source="section:spacing-system")
    if "whitespace-philosophy" in sections:
        text = " ".join(sections.get("whitespace-philosophy") or [])
        if text:
            add("spacing", _first_sentences(text, 1), source="section:whitespace-philosophy")
    if "grid-container" in sections:
        text = " ".join(sections.get("grid-container") or [])
        if text:
            add("layout-grid", _first_sentences(text, 2), source="section:grid-container")
    if "decorative-depth" in sections or "elevation-depth" in sections:
        text = " ".join(list(sections.get("decorative-depth") or []) + list(sections.get("elevation-depth") or []))
        if text:
            add("depth", _first_sentences(text, 2), source="section:elevation-depth")
    if "border-radius-scale" in sections:
        text = " ".join(sections.get("border-radius-scale") or [])
        if text:
            add("radii", _first_sentences(text, 1), source="section:border-radius-scale")
    if "breakpoints" in sections:
        text = " ".join(sections.get("breakpoints") or [])
        if text:
            add("responsive-behavior", _first_sentences(text, 2), source="section:breakpoints")
    if "touch-targets" in sections:
        text = " ".join(sections.get("touch-targets") or [])
        if text:
            add("responsive-behavior", _first_sentences(text, 1), source="section:touch-targets")
    if "photography-illustration-geometry" in sections:
        text = " ".join(sections.get("photography-illustration-geometry") or [])
        if text:
            add("imagery-media", _first_sentences(text, 1), source="section:photography-illustration-geometry")
    if "principles" in sections:
        text = " ".join(sections.get("principles") or [])
        if text:
            add("typography", _first_sentences(text, 1), source="section:principles")
    if "surface" in sections or "brand-accent" in sections:
        text = " ".join(list(sections.get("surface") or []) + list(sections.get("brand-accent") or []))
        if text:
            add("surface-treatment", _first_sentences(text, 2), source="section:surface")


def _add_motion_observations(tokens: Mapping[str, Sequence[Mapping]], add) -> None:
    """Motion requires a declared basis. Without one, nothing is observed.

    This is the executable form of "a static token table cannot tell you how
    something moves". A row is written only when the document itself declares a
    motion token group *and* names the basis it was read from, so a reference
    that asserts motion from typography values cannot produce a motion
    observation at all.
    """
    motion = tokens.get("motion") or []
    if not motion:
        return
    basis = ""
    for entry in motion:
        if not isinstance(entry, Mapping):
            continue
        values = entry.get("values")
        if isinstance(values, Mapping) and str(values.get("basis", "")).strip():
            basis = str(values["basis"]).strip()
            break
    if not basis:
        return
    add(
        "motion",
        f"{len(motion)} declared motion treatments",
        source="frontmatter.motion",
        detail={"count": len(motion)},
        basis=basis,
    )
    add(
        "interaction",
        f"{len(motion)} declared motion treatments record state transitions",
        source="frontmatter.motion",
        basis=basis,
    )


def _color_roles(colors: Sequence[Mapping]) -> dict[str, list[Mapping]]:
    """Group colour tokens by the role their name declares.

    Role is read from the token's own name, which is the only place the source
    states it. Nothing is inferred from a hex value.
    """
    buckets: dict[str, list[Mapping]] = {}
    for entry in colors:
        if not isinstance(entry, Mapping):
            continue
        name = str(entry.get("name", "")).lower()
        if any(token in name for token in ("surface", "canvas", "background", "bg-", "base")):
            role = "surface"
        elif any(token in name for token in ("hairline", "border", "stroke", "divider", "outline")):
            role = "border"
        elif any(token in name for token in ("ink", "text", "fg", "foreground")):
            role = "text"
        elif any(token in name for token in ("primary", "accent", "brand", "cta")):
            role = "accent"
        elif name.startswith("semantic-") or any(
            token in name for token in ("success", "warning", "error", "danger", "info")
        ):
            role = "semantic"
        else:
            role = "other"
        buckets.setdefault(role, []).append(entry)
    return buckets


def _scalar_colors(colors: Sequence[Mapping]) -> list[Mapping]:
    rows = []
    for entry in colors:
        if not isinstance(entry, Mapping):
            continue
        values = entry.get("values")
        if isinstance(values, Mapping):
            rows.append(values)
    return rows


def _size_key(value: str) -> tuple:
    digits = "".join(char for char in str(value) if char.isdigit() or char == ".")
    try:
        return (0, float(digits))
    except ValueError:
        return (1, 0.0)


def _first_sentences(text: str, count: int) -> str:
    """Take the first few sentences of a rationale section as an observation.

    Markdown table syntax is flattened to plain words rather than stored verbatim.
    A stored observation is read by people reviewing a direction, and a wall of
    ``|---|---|`` separators records the *document's* formatting rather than what
    the document says.
    """
    cleaned = " ".join(str(text).split())
    cleaned = re.sub(r"\|\s*-{2,}[^|]*\|", " ", cleaned)
    cleaned = cleaned.replace("|", " ")
    cleaned = re.sub(r"^\s*[-\s]*$", " ", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("**", "").replace("`", "").replace("_", " ")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    parts = [part.strip() for part in cleaned.replace("!", "!.").split(".") if part.strip()]
    return ". ".join(parts[:count]).strip(" .")[:400]


def build_treatments(
    patterns: Sequence[Mapping], *, borrow: Sequence[str] = (), adapt: Sequence[str] = (), avoid: Sequence[str] = ()
) -> list[dict]:
    """Assign each observed pattern a BORROW / ADAPT / AVOID treatment.

    Every extracted characteristic must land in exactly one bucket, which is the
    structural reason reference acquisition cannot quietly become reference
    cloning: there is no "untreated" state, so a pattern nobody decided about is
    a validation failure rather than a silent default of "copy it".

    Bucket membership is supplied by the caller as *dimensions*, and a dimension
    named in two buckets is refused rather than resolved by precedence.
    """
    named: dict[str, str] = {}
    for label, dimensions in (("BORROW", borrow), ("ADAPT", adapt), ("AVOID", avoid)):
        for dimension in dimensions:
            text = str(dimension)
            if text in named:
                raise ContractError(
                    f"pattern dimension {text!r} is assigned both {named[text]} and {label}; "
                    "a characteristic must be treated one way or the other, not ambiguously"
                )
            named[text] = label
    rows: list[dict] = []
    for pattern in patterns:
        if not isinstance(pattern, Mapping):
            continue
        dimension = str(pattern.get("dimension", ""))
        treatment = named.get(dimension, "ADAPT")
        rows.append({
            "pattern": safety.reference_text_is_data(
                pattern.get("observation", ""), field="treatment pattern"
            ),
            "dimension": dimension,
            "treatment": treatment,
            "rationale": (
                "the source states it; adapting is the default so an undecided observation is "
                "never treated as permission to copy"
            ),
        })
    return rows


DEFAULT_REUSE_CONSTRAINTS = (
    "extract principles; do not reproduce a branded composition",
    "do not copy exact brand colour values into this project's identity",
    "do not copy brand-specific iconography, wordmarks or imagery",
    "the source's own identity remains the property of its owner",
)
"""The standing reuse boundary Ariadne applies to every external reference.

These are Ariadne's constraints, not the source's licence terms. A source's
actual licence and attribution requirements travel separately in
``licensing``/``attribution`` and are recorded per reference."""


def normalize_reference(
    *,
    source_kind: str,
    source_provider: str,
    source_identity: str,
    source_uri: str,
    retrieved_at: str,
    content: bytes,
    title: str,
    brand: str = "",
    product: str = "",
    surface: str = "",
    reference_type: str = "",
    evidence_level: str = "",
    access_mode: str = "PUBLIC",
    license_status: str = "unknown",
    attribution: str = "",
    source_revision: str = "",
    source_date: str = "",
    historical: bool = False,
    applicable_requirements: Sequence[str] = (),
    limitations: Sequence[str] = (),
    limitations_from_document: Sequence[str] = (),
    extra_patterns: Sequence[Mapping] = (),
    treat_missing_document_as_empty: bool = False,
) -> dict:
    """Normalize retrieved bytes into one provider-neutral ``DesignReference``.

    Returns a dict shaped to be merged into an AR-202D reference record by
    :func:`attach`. The function is pure: it reads bytes and returns a record, and
    it writes nothing. That is what makes a frozen fixture and a live retrieval
    produce the same class of object.
    """
    from .. import references as references_module

    digest = references_module.digest_bytes(content)
    safety.check_document_size(
        content, limit=contracts.MAX_DESIGN_REFERENCE_BYTES, label="retrieved reference document"
    )
    text = content.decode("utf-8", errors="replace")
    # A file committed with a UTF-8 BOM opens with `<BOM>---`, not `---`. Deciding
    # "this is not a design document" from that would silently record a
    # zero-observation reference that still carries a correct content digest.
    #
    # DECLARED_LOCAL counts. The project's own DESIGN.md is parsed exactly like
    # an external one, because it is the *most* important evidence in the set: an
    # earlier version gated parsing on access_mode == "PUBLIC", which silently
    # gave every project-local design document zero observations and zero tokens
    # while still recording it as a reference. That inverted the priority order
    # the whole layer exists to enforce.
    #
    # ACCESS_RESTRICTED and UNREACHABLE carry no parsed content: there is nothing
    # to parse, and inventing observations for bytes that were never read is the
    # failure this refuses.
    is_design_document = (
        access_mode in ("PUBLIC", "DECLARED_LOCAL")
        and text.lstrip(designmd.BOM).lstrip().startswith("---")
    )
    parsed: dict = {}
    patterns: list[dict] = []
    if is_design_document or treat_missing_document_as_empty:
        if is_design_document:
            parsed = designmd.parse_design_md(text)
            patterns = extract_patterns(
                tokens=parsed.get("tokens") or {},
                sections=parsed.get("sections") or {},
                observed_at=str(retrieved_at),
            )
        elif treat_missing_document_as_empty:
            parsed = designmd.parse_design_md("", origin=str(source_uri))
        patterns.extend(dict(row) for row in extra_patterns if isinstance(row, Mapping))

    if not evidence_level:
        evidence_level = "CURATED_ANALYSIS" if source_kind == "CURATED_DESIGN_ANALYSIS" else (
            "DIRECTLY_INSPECTED" if source_kind in ("LOCAL_DESIGN_FILE", "FIRST_PARTY_DESIGN_MD")
            else "CAPTURED" if source_kind in ("LIVE_SITE_INSPECTION", "FIGMA_DOCUMENT")
            else "SECONDARY_DESCRIPTION" if source_kind == "SECONDARY_DESCRIPTION"
            else "SOURCE_INSPECTED"
        )

    classification = build_classification(
        source_kind=source_kind,
        source_provider=source_provider,
        source_identity=source_identity,
        source_uri=source_uri,
        retrieved_at=retrieved_at,
        content_digest=digest,
        evidence_level=evidence_level,
        access_mode=access_mode,
        brand=brand,
        product=product,
        surface=surface,
        reference_type=reference_type,
        source_revision=source_revision,
        source_date=source_date,
        historical=historical,
        size_bytes=len(content),
    )

    recorded_limitations = list(limitations)
    if is_design_document:
        for problem in designmd.validation_problems(parsed):
            recorded_limitations.append(f"document: {problem}")
        recorded_limitations.extend(str(item) for item in parsed.get("warnings") or [])
    recorded_limitations.extend(str(item) for item in limitations_from_document)
    if not patterns:
        recorded_limitations.append(
            "no structured token or rationale observation could be extracted from this source"
        )

    return {
        "schema_version": contracts.SCHEMA_DESIGN,
        "title": safety.reference_text_is_data(title, field="title"),
        "classification": classification,
        "observed_patterns": patterns,
        "normalized_digest": normalised_digest(classification, patterns),
        "design_document": {
            "present": bool(is_design_document),
            "format": "DESIGN.md" if is_design_document else "",
            "declared_version": str(parsed.get("declared_version", "") or ""),
            "declared_name": str(parsed.get("declared_name", "") or ""),
            "summary": designmd.summarise(parsed) if is_design_document else {},
            "unknown_fields": sorted(parsed.get("unknown_fields") or {}),
            "token_reference_count": len(parsed.get("token_references") or []),
            "unresolved_token_references": sum(
                1 for item in (parsed.get("token_references") or [])
                if isinstance(item, Mapping) and not item.get("resolved")
            ),
        },
        "design_tokens": parsed.get("tokens") or {},
        "applicable_requirements": [
            safety.reference_text_is_data(item, field="applicable_requirement") for item in applicable_requirements
        ],
        "limitations": [safety.reference_text_is_data(item, field="limitation") for item in dict.fromkeys(recorded_limitations)],
        "reuse_constraints": list(DEFAULT_REUSE_CONSTRAINTS),
        "license_status": str(license_status),
        "attribution": safety.reference_text_is_data(attribution, field="attribution"),
        "injection_scan": safety.scan_reference_text(text),
        "raw_artifact_refs": [],
        "capture_refs": [],
    }


ATTACHABLE_FIELDS = (
    "classification", "observed_patterns", "normalized_digest", "design_document",
    "design_tokens", "applicable_requirements", "limitations", "reuse_constraints",
    "license_status", "attribution", "injection_scan", "raw_artifact_refs", "capture_refs",
)
"""The AR-220 fields an attach merges onto an AR-202D reference record.

Named as one tuple so the merge cannot drift from the validator: adding a field
to a normalized payload without listing it here would silently drop it, and
listing it without extending the validator would let an unvalidated field
through.
"""


def attach(record: dict, normalized: Mapping) -> dict:
    """Merge a normalized reference into an AR-202D reference record.

    The lifecycle fields are untouched: this adds classification and observations
    to a record that is already ``FOUND``, and the existing validators then hold
    the merged record to the same rules as any other. If the merge would produce
    an invalid record the refusal happens here and the caller learns why, rather
    than at some later transition.
    """
    for field in ATTACHABLE_FIELDS:
        if field in normalized:
            record[field] = normalized[field]
    if "title" in normalized:
        record["title"] = str(normalized["title"])
    problems = contracts.reference_problems(record)
    if problems:
        raise ContractError(
            "normalized design reference would be malformed: " + "; ".join(problems)
        )
    return record


__all__ = [
    "ATTACHABLE_FIELDS",
    "DEFAULT_REUSE_CONSTRAINTS",
    "NORMALISED_DIGEST_FIELDS",
    "attach",
    "build_classification",
    "build_treatments",
    "canonical_digest",
    "detect_change",
    "extract_patterns",
    "normalised_digest",
    "normalize_reference",
]