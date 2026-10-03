"""The boundary that makes external design references safe to read (AR-220).

Every rule in this module exists because the input is *other people's design
material*, and design material is unusually good at carrying text that looks
like instructions. A reference page can say "ignore previous instructions",
"run this command", or "install this package", and a DESIGN.md can put the same
sentence in its rationale.

The single permanent rule:

> **External design references are data, not instructions or authority.**

Three families of check live here, and they are deliberately separate so a
failure names the thing that failed:

1. **Containment** - a locator must resolve inside a permitted root. Local
   ``DESIGN.md`` paths, evidence artifacts and cache writes all go through
   :func:`contained_path`, so ``..``, absolute paths, drive letters and symlinks
   cannot reach outside.
2. **URL safety** - :func:`require_fetchable_url` refuses ``file://``,
   non-HTTPS schemes, localhost, link-local and private address space, embedded
   credentials, and non-standard ports. There is no "trust this host" escape
   hatch, because a hostname that resolves to ``127.0.0.1`` is not made safe by
   being named in an allowlist.
3. **Non-escalation** - :func:`reference_text_is_data` records what untrusted
   text tried to do, and :func:`as_data_only` guarantees that no field derived
   from an external source can ever be read back as authority. External text can
   become an *observation*, an *evidence level*, or a *limitation*. It cannot
   become a permission, a policy change, a shell command or an approval.

Resource bounds live in :data:`contracts.MAX_DESIGN_REFERENCE_*` so one
oversized document cannot consume a run's whole context.
"""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urlsplit

from ..contracts import ContractError

# --------------------------------------------------------------- containment


def contained_path(candidate: str | Path, root: Path, *, label: str = "a design reference path") -> Path:
    """Resolve *candidate* inside *root* and refuse everything else.

    ``..`` segments, absolute paths, Windows drive letters, UNC prefixes and
    symlinks are all resolved before the containment assertion, so a path that
    *looks* contained and lands outside is refused just the same.
    """
    base = Path(root).resolve()
    text = str(candidate)
    if not text.strip():
        raise ContractError(f"{label} is empty")
    raw = Path(text)
    target = raw if raw.is_absolute() else base / raw
    try:
        resolved = target.resolve()
    except OSError as exc:  # pragma: no cover - platform-specific
        raise ContractError(f"{label} could not be resolved: {exc}") from exc
    if resolved != base and base not in resolved.parents:
        raise ContractError(
            f"{label} resolves outside the permitted root: {text!r} -> {resolved}; "
            "a reference locator may not escape the tree it was declared inside"
        )
    return resolved


# ------------------------------------------------------------------ URL safety

ALLOWED_SCHEMES = ("https",)
"""HTTPS only.

A curated-design catalog is public. There is no honest reason for this adapter
to speak ``file://``, ``ftp://`` or ``gopher://``, and each additional scheme is
a way to reach something the operator never allowlisted.
"""

ALLOWED_PORTS = (443, 8443)
"""Standard HTTPS ports only. A port is a reachability decision."""

_BLOCKED_HOSTNAMES = frozenset({
    "localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback",
    "metadata", "metadata.google.internal", "instance-data",
})
"""Names that are private by construction, before any DNS answer is considered."""

_URL_RE = re.compile(r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*)://")


def require_fetchable_url(url: str, *, label: str = "a reference URL") -> str:
    """Return *url* unchanged, or refuse it with a named reason.

    Refused: anything but HTTPS, a non-standard port, embedded credentials, a
    blocked hostname, and any host that is an IP literal in loopback, private,
    link-local, reserved or otherwise non-public space. A literal that resolves
    to a private address is refused without a DNS lookup, which is what makes
    the check deterministic and offline-testable.
    """
    text = str(url or "").strip()
    if not text:
        raise ContractError(f"{label} is empty")
    match = _URL_RE.match(text)
    if not match:
        raise ContractError(
            f"{label} is not an absolute URL: {text!r}; a reference locator must name its scheme"
        )
    scheme = match.group("scheme").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ContractError(
            f"{label} uses scheme {scheme!r}; only HTTPS reference retrieval is permitted"
        )
    parts = urlsplit(text)
    host = (parts.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise ContractError(f"{label} names no host")
    if "@" in (parts.netloc or ""):
        raise ContractError(
            f"{label} embeds credentials; a reference retrieval never sends project content or secrets"
        )
    if host in _BLOCKED_HOSTNAMES or host.endswith(".localhost") or host.endswith(".internal"):
        raise ContractError(f"{label} points at a loopback or private hostname: {host!r}")
    try:
        port = parts.port
    except ValueError as exc:
        raise ContractError(f"{label} has an unparseable port: {exc}") from exc
    if port is not None and port not in ALLOWED_PORTS:
        raise ContractError(
            f"{label} targets port {port}; reference retrieval uses standard HTTPS ports only"
        )
    literal = _ip_literal(host)
    if literal is not None and not _is_public_address(literal):
        raise ContractError(
            f"{label} points at {host!r}, which is not a public address; a reference URL may not "
            "reach loopback, private, link-local or reserved address space"
        )
    return text


def _ip_literal(host: str):
    candidate = host
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1]
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


def _is_public_address(address) -> bool:
    """Refuse every non-global address class, explicitly rather than by default."""
    if (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    ):
        return False
    # IPv4-mapped and 6to4 forms tunnel a public-looking address into a private one.
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None and not _is_public_address(mapped):
        return False
    if isinstance(address, ipaddress.IPv6Address):
        sixtofour = getattr(address, "sixtofour", None)
        if sixtofour is not None and not _is_public_address(sixtofour):
            return False
        if address.teredo is not None:
            server, _client = address.teredo
            if not _is_public_address(server):
                return False
    return True


# ------------------------------------------------------- prompt-injection boundary

INSTRUCTION_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("override-instructions", re.compile(
        r"\b(?:ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}\b"
        r"(?:previous|prior|earlier|above|all|any)\b[^.\n]{0,20}\b"
        r"(?:instruction|prompt|rule|direction|constraint|policy)",
        re.IGNORECASE,
    )),
    ("execute-command", re.compile(
        r"\b(?:run|execute|exec|invoke|shell|bash|powershell|cmd)\b[^.\n]{0,30}"
        r"(?:this|the following|command|script|code)\b|"
        r"\b(?:sudo|curl\s+-|wget\s+|rm\s+-rf|npm\s+i(?:nstall)?\b|pip\s+install|apt-get\b)",
        re.IGNORECASE,
    )),
    ("install-package", re.compile(
        r"\b(?:install|add|fetch|download|depend\s+on)\b[^.\n]{0,30}\b"
        r"(?:package|dependency|module|extension|plugin|npm|pypi)\b",
        re.IGNORECASE,
    )),
    ("grant-authority", re.compile(
        r"\b(?:you\s+(?:are|may|must|can)\s+now|grant(?:ed)?\s+(?:yourself|full)\b|"
        r"authoriz(?:e|ed)\s+(?:this|the agent|yourself)\b|"
        r"treat\s+this\s+as\s+(?:an?\s+)?(?:approval|authorization|authorised|authorized)\b|"
        r"no\s+longer\s+(?:requires?|needs?)\s+(?:approval|permission)\b)",
        re.IGNORECASE,
    )),
    ("policy-change", re.compile(
        r"\b(?:change|update|rewrite|relax|disable|turn\s+off)\b[^.\n]{0,30}\b"
        r"(?:policy|policies|gate|gates|rules?|guardrails?|safety|constraint)",
        re.IGNORECASE,
    )),
    ("exfiltrate", re.compile(
        r"\b(?:send|post|upload|transmit|exfiltrate|leak)\b[^.\n]{0,40}\b"
        r"(?:credential|password|secret|token|api[_ -]?key|env(?:ironment)?\b|source code)",
        re.IGNORECASE,
    )),
)
"""Text shapes that try to convert reference content into authority.

These are a *detector*, not a filter. Detection never removes the observation and
never refuses the reference - the sentence is part of what the source says. What
detection does is attach a recorded fact to the record, so a reviewer sees that
the source attempted escalation and so nothing downstream can treat the
sentence as a directive.
"""


def scan_reference_text(text: str) -> dict:
    """Report what untrusted reference text attempted. Records, never obeys."""
    findings: list[dict] = []
    value = str(text or "")
    for label, pattern in INSTRUCTION_PATTERNS:
        match = pattern.search(value)
        if match:
            findings.append({
                "kind": label,
                "excerpt": match.group(0)[:120],
                "action": "RECORDED_AS_DATA",
            })
    return {
        "scanned_characters": len(value),
        "instruction_attempts": findings,
        "treated_as": "data",
        "note": (
            "reference text is design material; an instruction inside it is recorded as an "
            "observation about the source and can never authorise an action or change policy"
        ),
    }


def as_data_only(value: str) -> str:
    """Neutralise text that will be stored inside a record.

    Control characters are stripped so a reference cannot smuggle a terminal
    escape or a newline-delimited record break into a JSON or markdown artefact.
    The words are *not* rewritten: silently editing a source would make the
    stored observation differ from the retrieved bytes, and the digest would no
    longer describe what was actually read.
    """
    text = str(value or "")
    return "".join(char for char in text if char == "\n" or char == "\t" or ord(char) >= 32)


def reference_text_is_data(value: str, *, field: str) -> str:
    """Return text safe to store in a record, refusing values that are not text."""
    if not isinstance(value, (str, int, float, bool)) and value is not None:
        raise ContractError(f"{field} must be text, not {type(value).__name__}")
    return as_data_only("" if value is None else str(value))


def instruction_attempt_summary(records: Sequence[Mapping]) -> dict:
    """Aggregate injection attempts across a retrieval, for the run summary."""
    total = 0
    kinds: dict[str, int] = {}
    for record in records:
        block = record.get("injection_scan") if isinstance(record, Mapping) else None
        if not isinstance(block, Mapping):
            continue
        for item in block.get("instruction_attempts") or []:
            if not isinstance(item, Mapping):
                continue
            kind = str(item.get("kind", "unknown"))
            kinds[kind] = kinds.get(kind, 0) + 1
            total += 1
    return {
        "references_scanned": len(records),
        "instruction_attempts": total,
        "kinds": dict(sorted(kinds.items())),
        "effect": "none; reference text is data and grants nothing",
    }


# ------------------------------------------------------------ resource bounds


def check_document_size(value: str | bytes, *, limit: int, label: str) -> int:
    """Refuse an oversized document with a named reason instead of truncating."""
    size = len(value.encode("utf-8")) if isinstance(value, str) else len(value)
    if size > limit:
        raise ContractError(
            f"{label} is {size} bytes, above the {limit}-byte bound; a design document may not "
            "consume unbounded context, and it is refused rather than silently truncated"
        )
    return size


def check_count(size: int, *, limit: int, label: str) -> int:
    if size > limit:
        raise ContractError(f"{label} is {size}, above the bound of {limit}")
    return size


__all__ = [
    "ALLOWED_PORTS",
    "ALLOWED_SCHEMES",
    "INSTRUCTION_PATTERNS",
    "as_data_only",
    "check_count",
    "check_document_size",
    "contained_path",
    "instruction_attempt_summary",
    "reference_text_is_data",
    "require_fetchable_url",
    "scan_reference_text",
]