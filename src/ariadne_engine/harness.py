"""The harness map: render the request Ariadne would actually send (AR-204 T1).

What this module can and cannot do
----------------------------------
AR-204's first rule is *measure the rendered request, not the template*. This
module reads an assembled stage packet and reports its real structure: the
sections in the order they are sent, each section's source bucket, measured byte
size, digest, stability and cacheability, plus the volatile values that sit inside
it. It also renders an arbitrary message/tool assembly into the same structure so
a provider adapter can inspect what it is about to send.

Two boundaries are deliberate:

* **The render is an inspection artifact.** It is not a request builder: nothing
  here is wired into the transport, so an inspection bug cannot alter what a
  worker receives. The map describes the packet the transport already produced.
* **Secrets are redacted on sight.** A render is a report, and a report must not
  leak a credential. :func:`redact` replaces a detected secret with a stable,
  non-reversible marker so two renders of the same secret compare equal without
  either containing the secret.

Unknown classifications are recorded as ``OTHER`` or ``UNKNOWN`` rather than
guessed, and byte counts are never converted into token counts.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from . import economics
from .serialization import (
    STABLE,
    VOLATILE,
    Memo,
    digest_bytes,
    digest_text,
    segment,
    stable_prefix,
)

# ----------------------------------------------------------------- redaction

REDACTION_PATTERNS: tuple[tuple[str, str], ...] = (
    # Provider keys and tokens. Ordered longest-prefix first so a specific key
    # shape is not partially matched by a broader one.
    ("anthropic-key", r"sk-ant-[A-Za-z0-9_\-]{16,}"),
    ("openai-key", r"sk-[A-Za-z0-9_\-]{20,}"),
    ("aws-access-key", r"AKIA[0-9A-Z]{16}"),
    ("google-key", r"AIza[0-9A-Za-z_\-]{30,}"),
    ("github-token", r"gh[pousr]_[A-Za-z0-9]{20,}"),
    ("slack-token", r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    ("bearer-token", r"(?i:bearer)\s+[A-Za-z0-9\-._~+/]{16,}=*"),
    ("private-key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    ("jwt", r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),
    ("assigned-secret", r"(?i:\b(?:api[_-]?key|secret|password|passwd|access[_-]?token|auth[_-]?token)\b)"
                        r"\s*[:=]\s*[\"']?([^\s\"',;]{8,})"),
)

_GROUP_NAMES = tuple(name.replace("-", "_") for name, _ in REDACTION_PATTERNS)
_COMBINED_REDACTION = re.compile(
    "|".join(f"(?P<{name}>{pattern})" for name, pattern in zip(_GROUP_NAMES, (item[1] for item in REDACTION_PATTERNS)))
)
_MARKER = re.compile(r"<REDACTED:[a-z\-]+:[0-9a-f]{8}>")


def redact(text: str) -> dict:
    """Replace detected secrets with a stable marker.

    The marker is ``<REDACTED:name:digest8>`` where the digest is over the secret
    itself. Two renders of the same secret therefore compare equal, and neither
    contains the secret. A redacted render can be compared, diffed and stored; the
    original is simply not present in it.

    All patterns are applied in a single pass over the original text, so one
    pattern can never match the marker another pattern just wrote.
    """
    value = str(text)
    counts: dict[str, int] = {}

    def replace(match: re.Match) -> str:
        name = str(match.lastgroup or "secret").replace("_", "-")
        counts[name] = counts.get(name, 0) + 1
        return f"<REDACTED:{name}:{digest_text(match.group(0))[:8]}>"

    redacted = _COMBINED_REDACTION.sub(replace, value)
    return {
        "text": redacted,
        "redactions": sum(counts.values()),
        "kinds": dict(sorted(counts.items())),
    }


# ----------------------------------------------------------------- section map

PACKET_PREAMBLE = "ARIADNE "

SECTION_HEADER = re.compile(
    r"^===== BEGIN (?P<label>.+?) \| SOURCE (?P<path>.+) \| "
    r"SOURCE-SHA256 (?P<source_sha256>[0-9a-f]{64}) \| "
    r"CONTENT-SHA256 (?P<content_sha256>[0-9a-f]{64}) =====$"
)
SECTION_FOOTER = re.compile(r"^===== END (?P<label>.+?) =====$")

_ANALYSIS_MEMO = Memo("harness-section-analysis")
"""A pure memo for the per-section redaction and volatility analysis.

The key is the digest of the analysed text and the dependency is that same digest,
so a different text can never be served from the entry: the worst case is a
recomputation, never a stale answer. The memo accelerates repeated renders of the
same packet; it is analysis only and no code path reads it for authority.
"""


def _analyse_section(raw: str) -> dict:
    """Redact and scan one section, memoised on its own digest."""
    encoded = raw.encode("utf-8")
    key = digest_bytes(encoded)
    dependency = {"sha256": key, "bytes": len(encoded)}
    hit = _ANALYSIS_MEMO.get(key, dependency)
    if hit is not None:
        return hit["value"]
    redacted = redact(raw)
    volatile = volatile_findings(redacted["text"])
    value = {
        "text": redacted["text"],
        "redactions": redacted["redactions"],
        "kinds": redacted["kinds"],
        "volatile": volatile,
    }
    _ANALYSIS_MEMO.put(key, dependency, value, kind="value")
    return value

_SECTION_ROLES = {
    "canonical-prompt": ("SYSTEM", "engine"),
    "canonical": ("POLICY", "policy"),
    "canonical-selected-skill": ("SKILLS", "policy"),
    "canonical-selected-capability": ("POLICY", "policy"),
    "canonical-prompt-block": ("SYSTEM", "engine"),
    "project": ("PROJECT_FACTS", "project"),
    "project-runtime": ("DESIGN_CONTEXT", "project"),
    "project-derived": ("PROJECT_FACTS", "project"),
    "continuation-restart-context": ("PREVIOUS_ATTEMPTS", "engine"),
    "continuation": ("PREVIOUS_ATTEMPTS", "engine"),
    "writing-input": ("TASK", "task"),
    "worker-validation": ("EVIDENCE", "relayer"),
    "worker-return": ("EVIDENCE", "worker"),
    "reference": ("RETRIEVED_SOURCE", "retrieved"),
    "retrieved": ("RETRIEVED_SOURCE", "retrieved"),
}
"""Transport ``kind`` -> (source bucket, origin). An unknown kind stays ``OTHER``."""

_BUCKET_OVERRIDES = (
    ("design-ledger", "DESIGN_CONTEXT"),
    ("creative-evidence", "DESIGN_CONTEXT"),
    ("capabilities.json", "POLICY"),
    ("handoff.md", "PROJECT_FACTS"),
    ("project.md", "PROJECT_FACTS"),
    ("design.md", "DESIGN_CONTEXT"),
    ("agents.md", "PROJECT_FACTS"),
    ("research.md", "PROJECT_FACTS"),
    ("qa.md", "POLICY"),
)


def classify_section(*, kind: str = "", path: str = "", label: str = "") -> dict:
    """Map one transport section onto a source bucket, with the reason recorded."""
    lowered = str(path).replace("\\", "/").lower()
    for marker, bucket in _BUCKET_OVERRIDES:
        if marker in lowered:
            return {"bucket": bucket, "origin": "project", "reason": f"path matches {marker}"}
    role = _SECTION_ROLES.get(str(kind))
    if role:
        return {"bucket": role[0], "origin": role[1], "reason": f"transport kind {kind!r}"}
    if str(label).strip().lower().startswith("current"):
        return {"bucket": "SYSTEM", "origin": "engine", "reason": "a current stage prompt block"}
    return {"bucket": "OTHER", "origin": "unknown", "reason": "no classification rule matched"}


# ---------------------------------------------------------------- volatility


VOLATILE_KINDS = (
    "timestamp",
    "record-id",
    "packet-reference",
    "source-commit",
    "baseline-head",
    "content-digest",
    "provider-identity",
    "environment-path",
)

PER_REQUEST_VOLATILE_KINDS = ("timestamp", "record-id", "packet-reference")
"""Values that change between two renders of the *same* revision.

A content digest, a source commit or a project path inside a delivered source is
not per-request volatile: the same revision renders it identically, which is what
a cache prefix needs. Only these three kinds make a delivered section unusable as
a reused prefix.
"""

SCAN_WINDOW_BYTES = 16_384
SCAN_TAIL_BYTES = 4_096
"""The volatility scan is bounded and says so.

Findings are reported over this window; the stability *decision* for a delivered
section does not depend on the scan, because the transport records a content
digest in the section header (content-addressed) and the header is always scanned.
"""

_VOLATILE_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("source-commit", re.compile(r"^Ariadne source commit: (?P<value>.+)$", re.M)),
    ("baseline-head", re.compile(r"^Baseline repository HEAD: (?P<value>.+)$", re.M)),
    ("record-id", re.compile(
        r"^(?:Packet ID|Task ID): (?P<value>.+)$"
        r"|\b(?:exe|dec|dcb|ctx|fail|ver|cap)_[0-9A-Za-z_\-]{6,}\b",
        re.M,
    )),
    ("provider-identity", re.compile(r"^Provider: (?P<value>.+)$", re.M)),
    ("packet-reference", re.compile(r"^Parent packet: (?P<value>.+)$", re.M)),
    ("content-digest", re.compile(r"\b[0-9a-f]{64}\b")),
    ("timestamp", re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b")),
    ("environment-path", re.compile(r"(?i)\b[A-Z]:[\\/](?:Users|Documents|AppData)[\\/][^\s\"']*")),
)


def volatile_findings(text: str, *, limit_per_kind: int = 3,
                      window_bytes: int = SCAN_WINDOW_BYTES,
                      tail_bytes: int = SCAN_TAIL_BYTES) -> dict:
    """Find the volatile values inside a rendered section.

    A volatile value is one that changes between two otherwise identical requests:
    a run/packet/execution id, a commit, a baseline head, a timestamp, a content
    digest or a machine-specific path. Finding them is what lets the cache plan
    say *why* a prefix is not reusable.

    The scan is bounded to a head window and a tail window of a long section, and
    the return value states the scanned byte count so a caller never reads a
    bounded scan as a complete one.
    """
    value = str(text)
    encoded = value.encode("utf-8")
    if len(encoded) <= window_bytes + tail_bytes:
        scanned, truncated = value, False
    else:
        scanned = (
            encoded[:window_bytes].decode("utf-8", errors="ignore")
            + "\n"
            + encoded[-tail_bytes:].decode("utf-8", errors="ignore")
        )
        truncated = True
    findings: list[dict] = []
    counts: dict[str, int] = {}
    for kind, pattern in _VOLATILE_PATTERNS:
        seen: list[str] = []
        for match in pattern.finditer(scanned):
            found = match.group(0)
            counts[kind] = counts.get(kind, 0) + 1
            if len(seen) < limit_per_kind:
                seen.append(
                    redact(found)["text"] if _may_be_secret(found) else found
                )
        if seen:
            findings.append({"kind": kind, "count": counts[kind], "samples": seen})
    return {
        "findings": findings,
        "kinds": sorted(counts),
        "volatile": bool(findings),
        "scanned_bytes": len(scanned.encode("utf-8")),
        "total_bytes": len(encoded),
        "complete_scan": not truncated,
    }


def _may_be_secret(value: str) -> bool:
    """A cheap check before running the full redaction patterns on a sample."""
    lowered = str(value).lower()
    return "=" in value or any(
        marker in lowered for marker in ("key", "token", "secret", "password", "bearer", "sk-", "akia")
    )


def section_stability(*, bucket: str, volatile: Mapping, cacheable: bool = True) -> str:
    """A section is volatile when it contains a per-request value, whatever its bucket."""
    if not cacheable:
        return VOLATILE
    if volatile.get("volatile"):
        return VOLATILE
    return STABLE


# ------------------------------------------------------------------ packet map


def _packet_lines(text: str) -> list[str]:
    return str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")


def packet_map(text: str, *, provider: str = "", model: str = "") -> dict:
    """The full harness map for one assembled packet.

    The map is read-only and offline. It reports the section order the transport
    produced, the preamble blocks (transport notice, worker contract, repair
    context) and the source sections, each with measured bytes, redaction, bucket,
    stability and volatility findings, then folds them into a stable-prefix plan.
    """
    lines = _packet_lines(text)
    preamble: list[str] = []
    sections: list[dict] = []
    current: dict | None = None
    for index, line in enumerate(lines):
        header = SECTION_HEADER.match(line)
        if header:
            current = {
                "label": header.group("label"),
                "path": header.group("path"),
                "source_sha256": header.group("source_sha256"),
                "content_sha256": header.group("content_sha256"),
                "start_line": index + 1,
                "lines": [],
            }
            sections.append(current)
            continue
        footer = SECTION_FOOTER.match(line)
        if footer and current is not None:
            current["end_line"] = index + 1
            current = None
            continue
        if current is None:
            preamble.append(line)
        else:
            current["lines"].append(line)
    rendered_sections: list[dict] = []
    for index, item in enumerate(sections):
        body = "\n".join(item["lines"]).rstrip("\n")
        kind = _kind_for(item["label"], item["path"])
        placement = classify_section(kind=kind, path=item["path"], label=item["label"])
        # The source section starts at its header line, which carries the hashes.
        header_text = (
            f"===== BEGIN {item['label']} | SOURCE {item['path']} | "
            f"SOURCE-SHA256 {item['source_sha256']} | CONTENT-SHA256 {item['content_sha256']} =====\n"
        )
        footer_text = f"\n===== END {item['label']} =====\n" if "end_line" in item else ""
        raw = header_text + body + footer_text
        analysis = _analyse_section(raw)
        redacted = {"text": analysis["text"], "redactions": analysis["redactions"], "kinds": analysis["kinds"]}
        volatile = analysis["volatile"]
        # A delivered section is content-addressed by its header digest, so two
        # renders of the same revision are byte-identical unless a per-request
        # value (a timestamp, a record id, a packet reference) is detected.
        per_request = sorted(set(volatile["kinds"]) & set(PER_REQUEST_VOLATILE_KINDS))
        content_addressed = bool(item["source_sha256"] and item["content_sha256"])
        if per_request:
            stability, basis = VOLATILE, "a per-request value was detected: " + ", ".join(per_request)
        elif content_addressed:
            stability, basis = STABLE, "the header records a content digest, so the section is content-addressed"
        else:
            stability, basis = VOLATILE, "the section carries no content digest, so reuse cannot be claimed"
        rendered_sections.append({
            "index": index,
            "label": item["label"],
            "path": item["path"],
            "kind": kind,
            "bucket": placement["bucket"],
            "origin": placement["origin"],
            "classification_reason": placement["reason"],
            "bytes": len(raw.encode("utf-8")),
            "redacted_bytes": len(redacted["text"].encode("utf-8")),
            "digest": digest_text(raw),
            "redactions": redacted["redactions"],
            "redaction_kinds": redacted["kinds"],
            "volatile": sorted(volatile["kinds"]),
            "per_request_volatile": per_request,
            "scan": {"scanned_bytes": volatile["scanned_bytes"], "total_bytes": volatile["total_bytes"],
                     "complete_scan": volatile["complete_scan"]},
            "stability": stability,
            "stability_basis": basis,
            "cacheable": stability == STABLE,
            "start_line": item["start_line"],
            "end_line": item.get("end_line"),
            "text": redacted["text"],
        })
    preamble_text = "\n".join(preamble).rstrip("\n")
    preamble_analysis = _analyse_section(preamble_text)
    preamble_redacted = {"text": preamble_analysis["text"],
                         "redactions": preamble_analysis["redactions"],
                         "kinds": preamble_analysis["kinds"]}
    preamble_volatile = preamble_analysis["volatile"]
    preamble_section = {
        "index": -1,
        "label": "packet preamble and transport scaffolding",
        "path": "",
        "kind": "transport",
        "bucket": "SYSTEM",
        "origin": "engine",
        "classification_reason": "transport-generated packet header and contract blocks",
        "bytes": len(preamble_text.encode("utf-8")),
        "redacted_bytes": len(preamble_redacted["text"].encode("utf-8")),
        "digest": digest_text(preamble_text),
        "redactions": preamble_redacted["redactions"],
        "redaction_kinds": preamble_redacted["kinds"],
        "volatile": sorted(preamble_volatile["kinds"]),
        "per_request_volatile": sorted(set(preamble_volatile["kinds"]) & set(PER_REQUEST_VOLATILE_KINDS)),
        "scan": {"scanned_bytes": preamble_volatile["scanned_bytes"],
                 "total_bytes": preamble_volatile["total_bytes"],
                 "complete_scan": preamble_volatile["complete_scan"]},
        "stability": VOLATILE,
        "stability_basis": "the transport scaffolding carries the packet identity and the repository head",
        "cacheable": False,
        "start_line": 1,
        "end_line": sections[0]["start_line"] - 1 if sections else len(lines),
        "text": preamble_redacted["text"],
    }
    ordered = [preamble_section, *rendered_sections]
    return _assemble_map(ordered, provider=provider, model=model)


def _kind_for(label: str, path: str) -> str:
    """Recover the transport kind label for a section from its label and path."""
    lowered = str(path).replace("\\", "/").lower()
    if "capabilities.json" in lowered:
        return "canonical-selected-capability"
    if lowered.startswith("skills/"):
        return "canonical-selected-skill" if "reference-analysis" in lowered or "component-research" in lowered else "canonical"
    if lowered.startswith("templates/"):
        return "canonical"
    if str(label).strip().lower().startswith("current"):
        return "canonical-prompt"
    if "restart" in str(label).lower():
        return "continuation-restart-context"
    if lowered.endswith(("project.md", "agents.md", "handoff.md", "research.md", "qa.md")):
        return "project"
    if lowered.endswith(".json"):
        return "project-runtime"
    return "project"


def _assemble_map(sections: Sequence[Mapping], *, provider: str, model: str) -> dict:
    segments = []
    rows = []
    for item in sections:
        segments.append(segment(
            str(item["segment_id"]) if item.get("segment_id") else f"section-{item['index']}",
            str(item.get("text", "")),
            stability=str(item.get("stability", STABLE)),
            cacheable=bool(item.get("cacheable", True)),
            role=str(item.get("bucket", "")),
        ))
        rows.append(economics.source_record(
            str(item.get("bucket", "OTHER")),
            origin=str(item.get("origin", "unknown")),
            label=str(item.get("label", "")),
            path=str(item.get("path", "")),
            bytes_measured=int(item.get("bytes", 0)),
            cacheability="CACHEABLE" if item.get("stability") == STABLE else "VOLATILE",
            reason=str(item.get("classification_reason", "")),
            usage="INCLUDED",
        ))
    plan = stable_prefix(segments)
    accounting = economics.source_accounting(rows)
    return {
        "schema_version": 1,
        "provider": str(provider),
        "model": str(model),
        "sections": [dict(item) for item in sections],
        "source_rows": rows,
        "source_buckets": accounting,
        "stable_prefix": {
            "stable_prefix_bytes": plan["stable_prefix_bytes"],
            "stable_prefix_digest": plan["stable_prefix_digest"],
            "volatile_bytes": plan["volatile_bytes"],
            "stable_segments": plan["stable_segments"],
            "volatile_segments": plan["volatile_segments"],
            "boundary_index": plan["boundary_index"],
        },
        "measured_size": {
            "total_bytes": sum(int(item.get("bytes", 0)) for item in sections),
            "rendered_bytes": plan["total_bytes"],
            "sections": len(sections),
            "redactions": sum(int(item.get("redactions", 0)) for item in sections),
        },
        "note": (
            "byte counts are measured locally; a render is redacted before it is reported and is never "
            "used to build a request"
        ),
    }


def packet_map_file(path: Path, *, provider: str = "", model: str = "") -> dict:
    return packet_map(Path(path).read_text(encoding="utf-8"), provider=provider, model=model)


# ------------------------------------------------------------ request rendering


def message(*, role: str, section: str, text: str, bucket: str = "OTHER", origin: str = "unknown",
            stability: str = STABLE, cacheable: bool | None = None) -> dict:
    """One message in a rendered request, with its bucket and stability."""
    if bucket not in economics.SOURCE_BUCKETS:
        raise ValueError(f"unknown source bucket: {bucket!r}")
    if stability not in (STABLE, VOLATILE):
        raise ValueError(f"unknown stability: {stability!r}")
    return {
        "role": str(role),
        "section": str(section),
        "bucket": bucket,
        "origin": origin,
        "stability": stability,
        "cacheable": (stability == STABLE) if cacheable is None else bool(cacheable),
        "text": str(text),
    }


def tool_schema(*, name: str, schema: Mapping, pack: str = "core") -> dict:
    """A tool declaration as the provider would receive it, with measured size."""
    from .serialization import canonical_bytes

    encoded = canonical_bytes(dict(schema))
    return {
        "name": str(name),
        "pack": str(pack),
        "schema": dict(schema),
        "bytes": len(encoded),
        "digest": digest_text(encoded.decode("utf-8")),
    }


def render_request(
    *,
    provider: str = "",
    model: str = "",
    messages: Sequence[Mapping],
    tools: Sequence[Mapping] = (),
    redact_output: bool = True,
) -> dict:
    """Render a request structure for inspection.

    The render mirrors the shape a provider adapter would send: ordered messages,
    tool declarations, the stable-prefix plan, the source-bucket accounting and
    the measured size. It is deliberately *not* a transport: no provider client is
    called, and no code path consumes the render to build a real request.
    """
    stable_segments = []
    volatile_segments = []
    rows = []
    rendered_messages = []
    for index, item in enumerate(messages):
        if not isinstance(item, Mapping):
            raise ValueError("a rendered message must be a mapping")
        bucket = str(item.get("bucket", "OTHER"))
        if bucket not in economics.SOURCE_BUCKETS:
            raise ValueError(f"unknown source bucket: {bucket!r}")
        text = str(item.get("text", ""))
        view = _analyse_section(text) if redact_output else {
            "text": text, "redactions": 0, "kinds": {},
        }
        stability = str(item.get("stability", STABLE))
        cacheable = bool(item.get("cacheable", stability == STABLE))
        target = stable_segments if stability == STABLE else volatile_segments
        target.append(segment(
            f"message-{index}",
            text,
            stability=stability,
            cacheable=cacheable,
            role=bucket,
        ))
        rows.append(economics.source_record(
            bucket,
            origin=str(item.get("origin", "unknown")),
            label=str(item.get("section", "")),
            bytes_measured=len(text.encode("utf-8")),
            cacheability="CACHEABLE" if stability == STABLE else "VOLATILE",
            reason="rendered as a request message",
            usage="INCLUDED",
        ))
        rendered_messages.append({
            "index": index,
            "role": str(item.get("role", "user")),
            "section": str(item.get("section", "")),
            "bucket": bucket,
            "origin": str(item.get("origin", "unknown")),
            "stability": stability,
            "cacheable": cacheable,
            "bytes": len(text.encode("utf-8")),
            "digest": digest_text(text),
            "text": view["text"],
            "redactions": view["redactions"],
            "redaction_kinds": view["kinds"],
        })
    plan = stable_prefix([*stable_segments, *volatile_segments])
    tool_rows = []
    for tool in tools:
        entry = dict(tool)
        if "bytes" not in entry:
            entry = tool_schema(name=str(entry.get("name", "")), schema=entry.get("schema", {}),
                                pack=str(entry.get("pack", "core")))
        tool_rows.append(entry)
    tool_bytes = sum(int(entry.get("bytes", 0)) for entry in tool_rows)
    accounting = economics.source_accounting(rows)
    if tool_rows:
        accounting = economics.source_accounting([
            *rows,
            *(economics.source_record(
                "TOOL_SCHEMAS",
                origin="engine",
                label=entry.get("name", ""),
                bytes_measured=int(entry.get("bytes", 0)),
                cacheability="CACHEABLE",
                reason="tool declaration sent with the request",
                usage="INCLUDED",
            ) for entry in tool_rows),
        ])
    return {
        "schema_version": 1,
        "kind": "ariadne-request-render",
        "provider": str(provider),
        "model": str(model),
        "messages": rendered_messages,
        "tools": tool_rows,
        "stable_prefix": {
            "stable_prefix_bytes": plan["stable_prefix_bytes"],
            "stable_prefix_digest": plan["stable_prefix_digest"],
            "volatile_bytes": plan["volatile_bytes"],
            "boundary_index": plan["boundary_index"],
            "stable_segments": plan["stable_segments"],
            "volatile_segments": plan["volatile_segments"],
        },
        "source_buckets": accounting,
        "volatile_sections": [
            item["section"] for item in rendered_messages if item["stability"] == VOLATILE
        ],
        "measured_size": {
            "total_bytes": plan["total_bytes"] + tool_bytes,
            "message_bytes": len(plan["stable_prefix_text"].encode("utf-8"))
            + len(plan["volatile_text"].encode("utf-8")),
            "tool_schema_bytes": tool_bytes,
            "messages": len(rendered_messages),
            "tools": len(tool_rows),
            "redactions": sum(item["redactions"] for item in rendered_messages),
        },
        "note": (
            "inspection only: this render is not a request builder, and secrets are redacted before "
            "they appear in it"
        ),
    }


def packet_render(text: str, *, provider: str = "", model: str = "") -> dict:
    """Render an assembled packet into the request-render structure."""
    mapping = packet_map(text, provider=provider, model=model)
    messages = [
        message(
            role="system" if item["bucket"] in ("SYSTEM", "POLICY", "SKILLS") else "user",
            section=str(item["label"]),
            text=str(item["text"]),
            bucket=str(item["bucket"]),
            origin=str(item["origin"]),
            stability=str(item["stability"]),
            cacheable=bool(item["cacheable"]),
        )
        for item in mapping["sections"]
    ]
    return render_request(provider=provider, model=model, messages=messages, tools=())


def source_bucket_totals(renders: Iterable[Mapping]) -> dict:
    """Aggregate source buckets across several renders."""
    render_rows = list(renders)
    totals: dict[str, dict] = {}
    for render in render_rows:
        block = render.get("source_buckets")
        if not isinstance(block, Mapping):
            continue
        for name, counters in (block.get("buckets") or {}).items():
            entry = totals.setdefault(str(name), {"sources": 0, "bytes": 0, "tokens": 0})
            entry["sources"] += int((counters or {}).get("sources", 0))
            entry["bytes"] += int((counters or {}).get("bytes", 0))
            entry["tokens"] += int((counters or {}).get("tokens", 0))
    return {"buckets": dict(sorted(totals.items())), "renders": len(render_rows)}


__all__ = [
    "REDACTION_PATTERNS",
    "VOLATILE_KINDS",
    "PACKET_PREAMBLE",
    "SECTION_HEADER",
    "SECTION_FOOTER",
    "redact",
    "classify_section",
    "volatile_findings",
    "section_stability",
    "packet_map",
    "packet_map_file",
    "message",
    "tool_schema",
    "render_request",
    "packet_render",
    "source_bucket_totals",
]
