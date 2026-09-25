"""Reference provenance, adapters and analysis (AR-202D T2/T3/T4).

The point of this module is that a design reference cannot be *asserted*. Every
state in the lifecycle is written here, in order, and each transition requires
the evidence the state means:

``FOUND`` ──→ ``ACCESSIBLE`` ──→ ``INSPECTED`` ──→ ``ANALYSED`` ──→ ``USED``
    └────────────────────────────→ ``INACCESSIBLE`` (blocker required, terminal)

Hard rules, enforced in code rather than prose:

* a URL existing is not an inspection, and a search-result snippet is not an
  analysis: the transitions are ordered and a caller cannot skip one;
* ``INSPECTED`` requires a real, hashed evidence artifact and at least one
  concrete observation;
* the *inspection type* (CONTENT / VISUAL / INTERACTION) bounds the claims the
  inspection can support, so a worker cannot upgrade a content reading into a
  behavioural claim by asserting it;
* ``ANALYSED`` requires an ``INSPECTED`` parent and every finding must cite an
  observation that inspection actually produced;
* ``USED`` requires an ``ANALYSED`` parent and a design decision anchored in a
  real artifact, so "mentioned in prose" can never become provenance;
* ``INACCESSIBLE`` is a first-class, valid outcome and the only terminal state
  that may carry a blocker instead of observations.

Adapters are read-only. None of them installs anything, posts anything, or
touches the project. None of them bypasses an access control, and the optional
paid provider is contract-only unless the operator has configured authorized
access, in which case it is still optional and never required.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from . import contracts
from .contracts import (
    REFERENCE_ADAPTER_CAPABILITIES,
    REFERENCE_ANALYSIS_DIMENSIONS,
    REFERENCE_DECISIONS,
    REFERENCE_INSPECTION_TYPES,
    REFERENCE_SOURCE_TYPES,
    REFERENCE_STATES,
    REFERENCE_TERMINAL_STATES,
    ContractError,
)

# --------------------------------------------------------------- claim kinds

CLAIM_KINDS = ("structure", "content", "appearance", "behaviour", "timing", "feedback")
"""What a design claim is *about*.

These are deliberately finer than the inspection types, because the whole point
of the distinction is that one kind of looking cannot support another kind of
claim.
"""

INSPECTION_SUPPORTS: dict[str, tuple[str, ...]] = {
    "CONTENT": ("structure", "content"),
    "VISUAL": ("appearance", "structure", "content"),
    "INTERACTION": ("behaviour", "timing", "feedback", "appearance"),
}
"""Which claim kinds each inspection type can support.

A ``CONTENT`` reading cannot support an ``appearance`` claim (nobody looked at a
rendering) and a screenshot cannot support a ``behaviour`` claim (nobody watched
it move). ``INTERACTION`` includes ``appearance`` because observing a live
interface necessarily includes seeing it.
"""

INSPECTION_LABELS = {
    "CONTENT": "content inspection",
    "VISUAL": "visual inspection",
    "INTERACTION": "interaction inspection",
}

TRANSITIONS: dict[str, frozenset[str]] = {
    "FOUND": frozenset({"ACCESSIBLE", "INACCESSIBLE"}),
    "ACCESSIBLE": frozenset({"INSPECTED", "INACCESSIBLE"}),
    "INSPECTED": frozenset({"INSPECTED", "ANALYSED"}),
    "ANALYSED": frozenset({"ANALYSED", "INSPECTED", "USED"}),
    "USED": frozenset(),
    "INACCESSIBLE": frozenset(),
}
"""The legal lifecycle moves. An illegal move is refused, never coerced.

``INACCESSIBLE`` is reachable only before anything was observed: once a real
inspection exists, "unreachable" is no longer the truth about the source and the
record keeps its evidence. The self-edges allow a second *distinct* inspection
(a reference seen but not driven can later be interaction-inspected) and a
re-analysis; duplicates are refused by the recording functions.
"""

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".svg")
_MEDIA_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif", ".svg": "image/svg+xml",
    ".html": "text/html", ".htm": "text/html", ".md": "text/markdown",
    ".txt": "text/plain", ".json": "application/json", ".css": "text/css",
    ".pdf": "application/pdf",
}

PROJECT_REFERENCE_DIRS = (Path("design") / "references", Path("references") / "design")
"""Where local reference material is expected to live inside a project."""

RETRIEVAL_MODES = contracts.REFERENCE_RETRIEVAL_MODES
"""How the bytes behind an ACCESSIBLE reference were obtained.

``local-read``          the engine re-read a local file and hashed it
``external-retrieval``  an adapter retrieved the bytes; a local digest does not
                        prove remote origin, and origin stays unproven until an
                        independent retrieval verification reproduces it
``fixture``             a declared deterministic fixture supplied the bytes
``declared``            a party asserted a digest; nothing was re-read

The mode is recorded so "the bytes existed once" is never mistaken for "the
engine can still produce them", and so a URL string is never treated as
retrieval proof.
"""

UNTRUSTED_TITLE_PATTERNS = (
    re.compile(r"^\s*$"),
    re.compile(r"^(best practice|industry standard|everyone does it)", re.IGNORECASE),
)
"""A title is a title. A claim is not a title."""


# ------------------------------------------------------------------ helpers

def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(Path(path).read_bytes())


def media_type(path: Path) -> str:
    return _MEDIA_TYPES.get(Path(path).suffix.lower(), "application/octet-stream")


def evidence_artifact(path: Path, *, project: Path | None = None) -> dict:
    """Hash one inspection/analysis artifact. Missing or empty files are refused.

    The artifact must be a real file: an inspection whose evidence does not exist
    is not an inspection, so this never fabricates a placeholder hash. When a
    permitted root is given the path is *resolved* (``..``, absolute paths,
    separators and symlinks included) and must land inside that root, so an
    out-of-root artifact cannot become provenance by being cited.
    """
    target = Path(path)
    if project is not None:
        target = contracts.contained_evidence_path(target, project, label="reference evidence")
    if not target.is_file():
        raise ContractError(f"reference evidence artifact does not exist: {target}")
    if target.stat().st_size <= 0:
        raise ContractError(f"reference evidence artifact is empty: {target}")
    return {"path": str(target.resolve()), "sha256": digest_file(target), "size": int(target.stat().st_size)}


def _state_history_entry(state: str, *, reason: str = "") -> dict:
    return {"state": state, "at": contracts.utc_now(), "reason": str(reason)}


# ------------------------------------------------------------------ adapters

@dataclass(frozen=True)
class ReferenceCandidate:
    """One candidate a discovery adapter returned. A candidate is not a reference."""

    source: str
    locator: str
    title: str
    source_type: str
    adapter: str
    retrieved_at: str = ""
    content: Mapping[str, object] = field(default_factory=dict)
    note: str = ""

    def as_record(self) -> dict:
        return {
            "source": self.source,
            "locator": self.locator,
            "title": self.title,
            "source_type": self.source_type,
            "adapter": self.adapter,
            "retrieved_at": self.retrieved_at,
            "content": dict(self.content),
            "note": self.note,
        }


class ReferenceAdapter:
    """Read-only reference source.

    An adapter declares what it can do and answers only for those capabilities.
    Calling an unsupported capability is refused by :meth:`require`, so a caller
    cannot obtain visual evidence from an adapter that never claimed to produce
    it.
    """

    id = "abstract"
    source_type = "fixture"
    kind = "reference"
    description = ""

    def capabilities(self) -> tuple[str, ...]:
        return ()

    def enabled(self) -> bool:
        return True

    def unavailable_reason(self) -> str:
        return ""

    def require(self, capability: str) -> None:
        if capability not in self.capabilities():
            raise ContractError(
                f"reference adapter {self.id!r} does not support capability {capability!r}; "
                "an adapter may not supply evidence it never declared"
            )

    # Each capability is optional; the base implementation refuses.
    def discover(self, query: Mapping) -> list[ReferenceCandidate]:
        self.require("discover")
        raise ContractError(f"{self.id} declares discover but implements nothing")

    def retrieve_metadata(self, candidate: ReferenceCandidate) -> dict:
        self.require("retrieve_metadata")
        raise ContractError(f"{self.id} declares retrieve_metadata but implements nothing")

    def retrieve_content(self, candidate: ReferenceCandidate) -> dict:
        self.require("retrieve_content")
        raise ContractError(f"{self.id} declares retrieve_content but implements nothing")

    def inspect_visual(self, candidate: ReferenceCandidate) -> dict:
        self.require("inspect_visual")
        raise ContractError(f"{self.id} declares inspect_visual but implements nothing")

    def inspect_interaction(self, candidate: ReferenceCandidate) -> dict:
        self.require("inspect_interaction")
        raise ContractError(f"{self.id} declares inspect_interaction but implements nothing")

    def capability_record(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "source_type": self.source_type,
            "description": self.description,
            "capabilities": list(self.capabilities()),
            "enabled": bool(self.enabled()),
            "unavailable_reason": self.unavailable_reason(),
        }


class UnavailableAdapter(ReferenceAdapter):
    """An adapter whose source is not configured or not authorized here.

    It is a *valid* adapter: it reports what it cannot do and why, and every
    retrieval attempt becomes a recorded ``INACCESSIBLE`` outcome with a blocker.
    It never fabricates evidence and never attempts a forbidden access.
    """

    def __init__(self, adapter_id: str, *, source_type: str, capabilities: Sequence[str],
                 reason: str, kind: str = "reference", description: str = "") -> None:
        self.id = adapter_id
        self.source_type = source_type
        self.kind = kind
        self.description = description or reason
        self._capabilities = tuple(capabilities)
        self._reason = reason

    def capabilities(self) -> tuple[str, ...]:
        return self._capabilities

    def enabled(self) -> bool:
        return False

    def unavailable_reason(self) -> str:
        return self._reason

    def _blocked(self, capability: str) -> dict:
        self.require(capability)
        return {"inaccessible": True, "blocker": self._reason, "adapter": self.id}

    def discover(self, query: Mapping) -> list[ReferenceCandidate]:
        return []

    def retrieve_metadata(self, candidate: ReferenceCandidate) -> dict:
        return self._blocked("retrieve_metadata")

    def retrieve_content(self, candidate: ReferenceCandidate) -> dict:
        return self._blocked("retrieve_content")

    def inspect_visual(self, candidate: ReferenceCandidate) -> dict:
        return self._blocked("inspect_visual")

    def inspect_interaction(self, candidate: ReferenceCandidate) -> dict:
        return self._blocked("inspect_interaction")


class LocalReferenceAdapter(ReferenceAdapter):
    """Files the operator placed in the project (``design/references/**``).

    Read-only, offline and always available. It can discover local material and
    hash it for content or visual inspection; it cannot and does not claim
    interaction inspection, because a file cannot show interaction.
    """

    id = "local-reference"
    source_type = "local-file"
    description = "project-local reference files and screenshots"

    def __init__(self, project: Path, *, roots: Sequence[Path] | None = None) -> None:
        self.project = Path(project)
        self.roots = [Path(root) for root in (roots or PROJECT_REFERENCE_DIRS)]

    def capabilities(self) -> tuple[str, ...]:
        return ("discover", "retrieve_metadata", "retrieve_content", "inspect_visual")

    def _files(self) -> list[Path]:
        found: list[Path] = []
        for relative in self.roots:
            base = self.project / relative
            if not base.is_dir():
                continue
            found.extend(sorted(path for path in base.rglob("*") if path.is_file()))
        return found

    def discover(self, query: Mapping) -> list[ReferenceCandidate]:
        needle = str((query or {}).get("query", "") or "").strip().lower()
        rows = []
        for path in self._files():
            relative = path.relative_to(self.project).as_posix()
            if needle and needle not in relative.lower():
                continue
            rows.append(ReferenceCandidate(
                source=relative,
                locator=str(path.resolve()),
                title=path.stem.replace("-", " ").replace("_", " "),
                source_type="project-screenshot" if path.suffix.lower() in _IMAGE_SUFFIXES else "local-file",
                adapter=self.id,
                note="discovered in the project reference directory",
            ))
        return rows

    def retrieve_metadata(self, candidate: ReferenceCandidate) -> dict:
        path = Path(candidate.locator)
        if not path.is_file():
            return {"inaccessible": True, "blocker": f"local reference file is missing: {path}"}
        return {
            "title": candidate.title,
            "mime": media_type(path),
            "size": int(path.stat().st_size),
            "content_sha256": digest_file(path),
            "access": "local-read-only",
        }

    def retrieve_content(self, candidate: ReferenceCandidate) -> dict:
        path = Path(candidate.locator)
        if not path.is_file():
            return {"inaccessible": True, "blocker": f"local reference file is missing: {path}"}
        return {
            "content_sha256": digest_file(path),
            "size": int(path.stat().st_size),
            "mime": media_type(path),
            "excerpt": _text_excerpt(path),
        }

    def inspect_visual(self, candidate: ReferenceCandidate) -> dict:
        path = Path(candidate.locator)
        if not path.is_file():
            return {"inaccessible": True, "blocker": f"local reference file is missing: {path}"}
        if path.suffix.lower() not in _IMAGE_SUFFIXES:
            return {
                "inaccessible": True,
                "blocker": (
                    f"{path.name} is not a visual artifact; reading a text or markup file is content "
                    "inspection, not visual inspection"
                ),
            }
        return {
            "artifact": str(path.resolve()),
            "content_sha256": digest_file(path),
            "mime": media_type(path),
            "rendered_by": "operator-supplied artifact",
        }


class ProjectDocumentAdapter(ReferenceAdapter):
    """The project's own design documents. Content inspection only."""

    id = "project-document"
    source_type = "project-document"
    description = "project documentation already in the repository"

    DOCUMENTS = ("PROJECT.md", "DESIGN.md", "RESEARCH.md", "HANDOFF.md")

    def __init__(self, project: Path, *, documents: Sequence[str] | None = None) -> None:
        self.project = Path(project)
        self.documents = tuple(documents or self.DOCUMENTS)

    def capabilities(self) -> tuple[str, ...]:
        return ("discover", "retrieve_metadata", "retrieve_content")

    def discover(self, query: Mapping) -> list[ReferenceCandidate]:
        rows = []
        for name in self.documents:
            path = self.project / name
            if path.is_file():
                rows.append(ReferenceCandidate(
                    source=name, locator=str(path.resolve()), title=name,
                    source_type="project-document", adapter=self.id,
                    note="project document",
                ))
        return rows

    def retrieve_metadata(self, candidate: ReferenceCandidate) -> dict:
        path = Path(candidate.locator)
        if not path.is_file():
            return {"inaccessible": True, "blocker": f"project document is missing: {candidate.source}"}
        return {
            "mime": media_type(path),
            "size": int(path.stat().st_size),
            "content_sha256": digest_file(path),
            "access": "project-read-only",
        }

    def retrieve_content(self, candidate: ReferenceCandidate) -> dict:
        path = Path(candidate.locator)
        if not path.is_file():
            return {"inaccessible": True, "blocker": f"project document is missing: {candidate.source}"}
        return {
            "content_sha256": digest_file(path),
            "size": int(path.stat().st_size),
            "mime": media_type(path),
            "excerpt": _text_excerpt(path),
        }


class FixtureReferenceAdapter(ReferenceAdapter):
    """Deterministic offline adapter for tests and benchmarks.

    A fixture is a JSON document that declares candidates and the evidence each
    one can produce. Nothing is fetched. A fixture that declares an inaccessible
    candidate stays inaccessible, which is the honest outcome the benchmarks
    assert on.
    """

    id = "fixture-reference"
    source_type = "fixture"
    description = "deterministic offline reference fixture"

    def __init__(self, payload: Mapping, *, fixture_root: Path | None = None) -> None:
        self.payload = dict(payload or {})
        self.fixture_root = Path(fixture_root) if fixture_root is not None else None
        self._candidates = [dict(item) for item in (self.payload.get("candidates") or []) if isinstance(item, Mapping)]

    def capabilities(self) -> tuple[str, ...]:
        declared = self.payload.get("capabilities")
        if isinstance(declared, list) and declared:
            return tuple(str(item) for item in declared)
        return ("discover", "retrieve_metadata", "retrieve_content", "inspect_visual", "inspect_interaction")

    def unavailable_reason(self) -> str:
        return str(self.payload.get("unavailable_reason", "") or "")

    def enabled(self) -> bool:
        return bool(self.payload.get("enabled", True))

    def discover(self, query: Mapping) -> list[ReferenceCandidate]:
        rows = []
        for item in self._candidates:
            rows.append(ReferenceCandidate(
                source=str(item.get("source", "")),
                locator=str(item.get("locator", "")),
                title=str(item.get("title", "")),
                source_type=str(item.get("source_type", "fixture")),
                adapter=self.id,
                note=str(item.get("note", "")),
            ))
        return rows

    def _entry(self, candidate: ReferenceCandidate) -> dict:
        for item in self._candidates:
            if str(item.get("source", "")) == candidate.source:
                return item
        return {}

    def _artifact(self, entry: Mapping, key: str) -> tuple[str, str]:
        """(path, blocker). A declared artifact is hashed, never invented."""
        declared = entry.get(key)
        if not isinstance(declared, Mapping):
            raise ContractError(f"fixture entry {entry.get('source')!r} declares no {key}")
        value = str(declared.get("path", ""))
        path = Path(value)
        if not path.is_absolute() and self.fixture_root is not None:
            path = self.fixture_root / value
        if not path.is_file():
            return "", f"fixture artifact is missing: {value}"
        return str(path.resolve()), ""

    def retrieve_metadata(self, candidate: ReferenceCandidate) -> dict:
        entry = self._entry(candidate)
        if entry.get("inaccessible"):
            return {"inaccessible": True, "blocker": str(entry.get("blocker", "fixture declares this source inaccessible"))}
        artifact, blocker = self._artifact(entry, "metadata")
        if blocker:
            return {"inaccessible": True, "blocker": blocker}
        return {
            "title": str(entry.get("title", candidate.title)),
            "mime": str(entry.get("mime", "application/octet-stream")),
            "size": int(Path(artifact).stat().st_size),
            "content_sha256": digest_file(Path(artifact)),
            "access": "fixture-read-only",
        }

    def retrieve_content(self, candidate: ReferenceCandidate) -> dict:
        entry = self._entry(candidate)
        if entry.get("inaccessible"):
            return {"inaccessible": True, "blocker": str(entry.get("blocker", "fixture declares this source inaccessible"))}
        artifact, blocker = self._artifact(entry, "content")
        if blocker:
            return {"inaccessible": True, "blocker": blocker}
        return {
            "content_sha256": digest_file(Path(artifact)),
            "size": int(Path(artifact).stat().st_size),
            "mime": str(entry.get("mime", "text/plain")),
            "excerpt": _text_excerpt(Path(artifact)),
        }

    def inspect_visual(self, candidate: ReferenceCandidate) -> dict:
        entry = self._entry(candidate)
        if entry.get("inaccessible"):
            return {"inaccessible": True, "blocker": str(entry.get("blocker", "fixture declares this source inaccessible"))}
        if not entry.get("visual"):
            return {
                "inaccessible": True,
                "blocker": "the fixture declares no visual artifact for this source",
            }
        artifact, blocker = self._artifact(entry, "visual")
        if blocker:
            return {"inaccessible": True, "blocker": blocker}
        return {
            "artifact": artifact,
            "content_sha256": digest_file(Path(artifact)),
            "mime": str(entry.get("mime", "image/png")),
            "rendered_by": "fixture capture",
        }

    def inspect_interaction(self, candidate: ReferenceCandidate) -> dict:
        entry = self._entry(candidate)
        if entry.get("inaccessible"):
            return {"inaccessible": True, "blocker": str(entry.get("blocker", "fixture declares this source inaccessible"))}
        interaction = entry.get("interaction")
        if not isinstance(interaction, Mapping):
            return {
                "inaccessible": True,
                "blocker": "the fixture declares no interaction transcript for this source",
            }
        artifact, blocker = self._artifact(entry, "interaction")
        if blocker:
            return {"inaccessible": True, "blocker": blocker}
        return {
            "artifact": artifact,
            "content_sha256": digest_file(Path(artifact)),
            "steps": [str(item) for item in (interaction.get("steps") or [])],
        }


def _text_excerpt(path: Path, limit: int = 400) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return re.sub(r"\s+", " ", text[:limit]).strip()


class ApprovedUrlAdapter(ReferenceAdapter):
    """Operator-approved public URLs.

    AR-202D implements the *contract* and the refusal. A live fetch happens only
    when the runtime is explicitly given an authorized fetch capability, and even
    then the discipline stays: HTTPS only, an explicit allowlist, content-type
    allowlist, byte cap, no credentials, no project content in the request, and
    robots/access restrictions honoured. Without that capability this adapter is
    disabled and every attempt becomes a recorded ``INACCESSIBLE`` outcome.
    """

    id = "approved-url"
    source_type = "approved-url"
    description = "operator-approved public web references (HTTPS, allowlisted)"

    def __init__(self, project: Path, *, allowlist: Sequence[str] = (), fetcher=None,
                 reason: str = "") -> None:
        self.project = Path(project)
        self.allowlist = tuple(str(item) for item in allowlist)
        self.fetcher = fetcher
        self._reason = reason or (
            "no authorized web retrieval capability is configured; Ariadne does not scrape, "
            "bypass authentication or fetch without an operator-approved allowlist"
        )

    def capabilities(self) -> tuple[str, ...]:
        base = ("discover", "retrieve_metadata", "retrieve_content")
        return base + (("inspect_visual",) if self.fetcher is not None else ())

    def enabled(self) -> bool:
        return self.fetcher is not None and bool(self.allowlist)

    def unavailable_reason(self) -> str:
        return "" if self.enabled() else self._reason

    def _blocked(self) -> dict:
        return {"inaccessible": True, "blocker": self._reason, "adapter": self.id}

    def discover(self, query: Mapping) -> list[ReferenceCandidate]:
        if not self.enabled():
            return []
        needle = str((query or {}).get("query", "") or "")
        return [
            ReferenceCandidate(
                source=url, locator=url, title=url, source_type="approved-url",
                adapter=self.id, note=f"approved URL matching {needle!r}" if needle else "approved URL",
            )
            for url in self.allowlist
        ]

    def retrieve_metadata(self, candidate: ReferenceCandidate) -> dict:
        if not self.enabled() or candidate.locator not in self.allowlist:
            return self._blocked()
        return dict(self.fetcher(candidate, "metadata"))

    def retrieve_content(self, candidate: ReferenceCandidate) -> dict:
        if not self.enabled() or candidate.locator not in self.allowlist:
            return self._blocked()
        return dict(self.fetcher(candidate, "content"))

    def inspect_visual(self, candidate: ReferenceCandidate) -> dict:
        if not self.enabled() or candidate.locator not in self.allowlist:
            return self._blocked()
        return dict(self.fetcher(candidate, "visual"))


class OptionalProviderAdapter(ReferenceAdapter):
    """A paid design library (Mobbin-class), contract-only by default.

    AR-202D never bundles, requires or pays for it. If the operator configures an
    authorized licensed interface, the adapter becomes usable through that
    interface; otherwise every call is a recorded, honest ``INACCESSIBLE`` and
    the rest of Ariadne works exactly as well without it. There is no scraping
    path in this class and no place to put one.
    """

    id = "paid-design-library"
    source_type = "paid-provider"

    def __init__(self, *, provider: str = "mobbin", licensed_interface=None,
                 licence_reference: str = "", reason: str = "") -> None:
        self.provider = provider
        self.licensed_interface = licensed_interface
        self.licence_reference = licence_reference
        self.description = f"optional licensed {provider}-class provider"
        self._reason = reason or (
            f"no authorized licensed {provider} access is configured in this environment; the provider "
            "is optional and Ariadne provides design intelligence without it"
        )

    def capabilities(self) -> tuple[str, ...]:
        if self.licensed_interface is None:
            return ()
        return ("discover", "retrieve_metadata", "retrieve_content", "inspect_visual")

    def enabled(self) -> bool:
        return self.licensed_interface is not None and bool(self.licence_reference)

    def unavailable_reason(self) -> str:
        return "" if self.enabled() else self._reason

    def discover(self, query: Mapping) -> list[ReferenceCandidate]:
        if not self.enabled():
            return []
        return list(self.licensed_interface.discover(query))

    def retrieve_metadata(self, candidate: ReferenceCandidate) -> dict:
        if not self.enabled():
            return {"inaccessible": True, "blocker": self._reason, "adapter": self.id}
        return dict(self.licensed_interface.retrieve_metadata(candidate))

    def retrieve_content(self, candidate: ReferenceCandidate) -> dict:
        if not self.enabled():
            return {"inaccessible": True, "blocker": self._reason, "adapter": self.id}
        return dict(self.licensed_interface.retrieve_content(candidate))

    def inspect_visual(self, candidate: ReferenceCandidate) -> dict:
        if not self.enabled():
            return {"inaccessible": True, "blocker": self._reason, "adapter": self.id}
        return dict(self.licensed_interface.inspect_visual(candidate))


# ----------------------------------------------------------------- registry

def default_adapters(project: Path, *, fixture: Mapping | None = None,
                     fixture_root: Path | None = None) -> dict[str, ReferenceAdapter]:
    """Every adapter AR-202D ships, each reporting its own honest availability."""
    adapters: list[ReferenceAdapter] = [
        LocalReferenceAdapter(project),
        ProjectDocumentAdapter(project),
        ApprovedUrlAdapter(project),
        OptionalProviderAdapter(),
    ]
    if fixture is not None:
        adapters.insert(0, FixtureReferenceAdapter(fixture, fixture_root=fixture_root))
    return {adapter.id: adapter for adapter in adapters}


def capability_matrix(adapters: Mapping[str, ReferenceAdapter]) -> list[dict]:
    """The declared capability record for every adapter. Never inferred from branding."""
    return [adapter.capability_record() for adapter in adapters.values()]


def require_source_type(value: str) -> str:
    if value not in REFERENCE_SOURCE_TYPES:
        raise ContractError(f"unsupported reference source type: {value!r}")
    return value


# --------------------------------------------------------------- record I/O

def references(state: dict) -> list[dict]:
    values = state.get("design_references")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def reference(state: dict, reference_id: str) -> dict | None:
    for record in references(state):
        if str(record.get("reference_id", "")) == str(reference_id):
            return record
    return None


def _require(state: dict, reference_id: str) -> dict:
    record = reference(state, reference_id)
    if record is None:
        raise ContractError(f"no reference record matches {reference_id!r}")
    return record


def _transition(record: dict, target: str, *, reason: str = "", updates: Mapping | None = None) -> None:
    """Validate one lifecycle move and commit it atomically.

    Nothing is written to the record until the move is legal *and* the record
    with the intended payload passes structural validation. A refused call
    therefore leaves the record byte-identical, which is what ``ContractError``
    promises its callers; callers pass their payload as ``updates`` instead of
    mutating first and asking afterwards.
    """
    current = str(record.get("state", ""))
    if target not in TRANSITIONS.get(current, frozenset()):
        raise ContractError(
            f"reference {record.get('reference_id')} cannot move {current} -> {target}; "
            "the provenance lifecycle is ordered and cannot be skipped"
        )
    if current in REFERENCE_TERMINAL_STATES:
        raise ContractError(
            f"reference {record.get('reference_id')} is {current}; a terminal reference state is not rewritten"
        )
    history = list(record.get("state_history") or [])
    if len(history) >= contracts.MAX_REFERENCE_HISTORY:
        raise ContractError(
            f"reference {record.get('reference_id')} has reached its lifecycle-history bound "
            f"({contracts.MAX_REFERENCE_HISTORY} transitions); further transitions are refused"
        )
    candidate = dict(record)
    if updates:
        candidate.update(updates)
    candidate["state"] = target
    candidate["state_history"] = history + [_state_history_entry(target, reason=reason)]
    problems = contracts.reference_problems(candidate)
    if problems:
        raise ContractError("reference record would be malformed: " + "; ".join(problems))
    record.update(candidate)


def register(
    state: dict,
    *,
    source: str,
    locator: str,
    title: str,
    source_type: str,
    adapter: str,
    task_id: str = "",
    query: str = "",
    licensing: Mapping | None = None,
    revision_hash: str = "",
) -> dict:
    """Record a ``FOUND`` reference. Nothing about its content is claimed."""
    if not str(source or "").strip():
        raise ContractError("a reference needs a source name")
    if not str(locator or "").strip():
        raise ContractError("a reference needs a locator")
    if any(pattern.match(str(title or "")) for pattern in UNTRUSTED_TITLE_PATTERNS):
        raise ContractError(
            "a reference title must describe the source, not assert a claim about it"
        )
    record = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "reference_id": contracts.new_record_id("ref"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "source": str(source),
        "source_type": require_source_type(source_type),
        "locator": str(locator),
        "title": str(title),
        "adapter": str(adapter),
        "query": str(query),
        "state": "FOUND",
        "state_history": [_state_history_entry("FOUND", reason="discovered")],
        "recorded_at": contracts.utc_now(),
        "retrieved_at": "",
        "content": {},
        "inspections": [],
        "analysis": None,
        "usage": None,
        "blocker": "",
        "licensing": dict(licensing or {}),
        "revision_hash": str(revision_hash),
        "provenance": {
            "created_by": "engine",
            "policy_version": contracts.POLICY_VERSION,
            "discovery": "adapter-discovery" if query else "declared",
        },
    }
    problems = contracts.reference_problems(record)
    if problems:
        raise ContractError("reference record is malformed: " + "; ".join(problems))
    contracts.require_design_capacity(state, "design_references")
    state.setdefault("design_references", []).append(record)
    return record


def mark_accessible(
    state: dict,
    reference_id: str,
    *,
    content_sha256: str,
    size: int = 0,
    mime: str = "",
    retrieved_at: str = "",
    licence_note: str = "",
    adapter: str = "",
) -> dict:
    """Record that the bytes/interface were actually reachable. No observation yet."""
    record = _require(state, reference_id)
    if not re.fullmatch(r"[0-9a-f]{64}", str(content_sha256 or "")):
        raise ContractError("an accessible reference needs the retrieved content digest")
    digest_source = "declared"
    retrieval_mode = "declared"
    if str(record.get("source_type", "")) in ("local-file", "project-screenshot", "project-document"):
        # The locator is caller-supplied, so it is contained like every other
        # artifact this engine reads: a local source that resolves outside the
        # project cannot be re-read and blessed as engine-verified provenance.
        target = contracts.contained_evidence_path(
            record.get("locator", ""),
            contracts.permitted_project_root(state, label="a local source"),
            label="a local source",
        )
        if not target.is_file():
            raise ContractError(
                f"the local source {target} does not exist; a local reference that cannot be read is "
                "inaccessible, not accessible"
            )
        try:
            computed = digest_file(target)
        except OSError as exc:
            raise ContractError(f"the local source {target} could not be read: {exc}") from exc
        if computed != str(content_sha256):
            raise ContractError(
                "the supplied retrieval digest does not match the local source; a local source is "
                "re-read and hashed, so its digest cannot be asserted"
            )
        digest_source = "local-verified"
        retrieval_mode = "local-read"
    elif str(record.get("source_type", "")) == "fixture":
        retrieval_mode = "fixture"
    elif str(record.get("source_type", "")) in ("approved-url", "official-api", "paid-provider"):
        retrieval_mode = "external-retrieval"
    licensing = dict(record.get("licensing") or {})
    if licence_note:
        licensing["note"] = str(licence_note)
    access = dict(record.get("access") or {})
    if adapter:
        access["adapter"] = str(adapter)
    _transition(record, "ACCESSIBLE", reason="retrieval produced a content digest", updates={
        "retrieved_at": str(retrieved_at or contracts.utc_now()),
        "content": {
            "sha256": str(content_sha256),
            "size": int(size or 0),
            "mime": str(mime),
            "digest_source": digest_source,
            "retrieval_mode": retrieval_mode,
            "origin": {
                "locator": str(record.get("locator", "")),
                "remote_origin_proven": False,
                "note": (
                    "a local digest proves the bytes existed here; it does not prove the remote "
                    "origin unless an independent retrieval verification reproduces it"
                ),
            },
        },
        "licensing": licensing,
        "access": access,
    })
    return record


def mark_inaccessible(
    state: dict,
    reference_id: str,
    *,
    blocker: str,
    adapter: str = "",
) -> dict:
    """Terminal, valid outcome: the source could not be reached. A blocker is required."""
    record = _require(state, reference_id)
    if not str(blocker or "").strip():
        raise ContractError("an inaccessible reference must record a blocker")
    access = dict(record.get("access") or {})
    if adapter:
        access["adapter"] = str(adapter)
    _transition(record, "INACCESSIBLE", reason=str(blocker), updates={
        "blocker": str(blocker),
        "access": access,
    })
    return record


def inspect(
    state: dict,
    reference_id: str,
    *,
    inspection_type: str,
    observations: Sequence[str],
    evidence_path: Path,
    project: Path | None = None,
    claim_kinds: Sequence[str] = (),
    viewport: Mapping | None = None,
    mechanisms: Sequence[str] = (),
    note: str = "",
) -> dict:
    """Record one inspection. Evidence, observations and claim bounds are enforced."""
    record = _require(state, reference_id)
    kind = str(inspection_type or "").upper()
    if kind not in REFERENCE_INSPECTION_TYPES:
        raise ContractError(
            f"unsupported inspection type {inspection_type!r}; expected one of "
            + ", ".join(REFERENCE_INSPECTION_TYPES)
        )
    clean_observations = [str(item).strip() for item in (observations or []) if str(item).strip()]
    if not clean_observations:
        raise ContractError(
            f"a {INSPECTION_LABELS[kind].lower()} must record at least one concrete observation"
        )
    claims = [str(item).strip().lower().replace("_", "-") for item in (claim_kinds or []) if str(item).strip()]
    unknown_claims = [item for item in claims if item not in CLAIM_KINDS]
    if unknown_claims:
        raise ContractError("unknown claim kind(s): " + ", ".join(sorted(unknown_claims)))
    supported = set(INSPECTION_SUPPORTS[kind])
    excess = sorted(set(claims) - supported)
    if excess:
        raise ContractError(
            f"a {INSPECTION_LABELS[kind].lower()} cannot support "
            + ", ".join(excess)
            + " claim(s); the claim kind exceeds the evidence and cannot be established by assertion"
        )
    mechanisms_list = [str(item).strip() for item in (mechanisms or []) if str(item).strip()]
    if len(mechanisms_list) > 2:
        raise ContractError("an inspection may record at most two mechanisms")
    artifact = evidence_artifact(Path(evidence_path), project=project)
    entry = {
        "inspection_id": contracts.new_record_id("ins"),
        "type": kind,
        "inspected_at": contracts.utc_now(),
        "observations": clean_observations,
        "claim_kinds": claims or sorted(supported),
        "mechanisms": mechanisms_list,
        "evidence": artifact,
        "note": str(note),
    }
    if viewport is not None:
        entry["viewport"] = dict(viewport)
    existing = [item for item in (record.get("inspections") or []) if isinstance(item, Mapping)]
    for item in existing:
        same_type = str(item.get("type")) == kind
        same_evidence = str((item.get("evidence") or {}).get("sha256", "")) == artifact["sha256"]
        same_viewport = (item.get("viewport") or {}) == (entry.get("viewport") or {})
        if same_type and same_evidence and same_viewport:
            raise ContractError(
                f"reference {reference_id} already has an identical {kind.lower()} inspection; "
                "re-recording the same evidence adds no provenance"
            )
    access = dict(record.get("access") or {})
    access.setdefault("adapter", str(record.get("adapter", "")))
    _transition(record, "INSPECTED", reason=f"{kind.lower()} inspection with {len(clean_observations)} observation(s)",
                updates={"inspections": existing + [entry], "access": access})
    return record


def analyse(
    state: dict,
    reference_id: str,
    *,
    findings: Sequence[Mapping],
    note: str = "",
) -> dict:
    """Generalise observations into design implications. Requires an INSPECTED parent."""
    record = _require(state, reference_id)
    current = str(record.get("state", ""))
    if current not in ("INSPECTED", "ANALYSED"):
        raise ContractError(
            "a reference must be INSPECTED before it can be ANALYSED; a search result or a "
            "retrieved page is not an analysis"
        )
    known_inspections = {
        str(item.get("inspection_id")): item for item in (record.get("inspections") or []) if isinstance(item, Mapping)
    }
    rows = [dict(item) for item in (findings or []) if isinstance(item, Mapping)]
    if not rows:
        raise ContractError("a reference analysis must record at least one finding")
    for row in rows:
        dimension = str(row.get("dimension", "")).strip()
        if dimension not in REFERENCE_ANALYSIS_DIMENSIONS:
            raise ContractError(f"unknown reference analysis dimension: {dimension!r}")
        for name in ("observation", "interpretation", "applicability"):
            if not str(row.get(name, "")).strip():
                raise ContractError(
                    f"an analysis finding must separate its {name} from its neighbours "
                    f"(missing {name} on {dimension})"
                )
        decision = str(row.get("decision", "")).strip()
        if decision not in REFERENCE_DECISIONS:
            raise ContractError(f"an analysis finding must record an adoption decision, not {decision!r}")
        citations = [str(item) for item in (row.get("inspection_ids") or [])]
        if not citations:
            raise ContractError(
                f"an analysis finding on {dimension} cites no observation; an analysis must derive "
                "from an inspection that happened"
            )
        unknown = [item for item in citations if item not in known_inspections]
        if unknown:
            raise ContractError(
                "analysis cites inspections that this reference does not have: " + ", ".join(unknown)
            )
        claim = str(row.get("claim_kind", "")).strip().lower().replace("_", "-")
        if claim and claim not in CLAIM_KINDS:
            raise ContractError(f"unknown claim kind: {claim!r}")
        if claim:
            allowed = set()
            for item in citations:
                allowed |= set(known_inspections[item].get("claim_kinds") or [])
            if claim not in allowed:
                raise ContractError(
                    f"the analysis claims {claim} but the cited inspection(s) never established it; "
                    "an inspection type cannot be upgraded by assertion"
                )
        if decision == "adopted" and not str(row.get("mechanism", "")).strip():
            raise ContractError(
                f"an adopted finding on {dimension} must name the mechanism it relies on; "
                "'others do it' is not a mechanism"
            )
    analysis = {
        # the analysis carries the same identifying fields it would have standalone,
        # so one validator describes one shape wherever that shape appears
        "schema_version": contracts.SCHEMA_DESIGN,
        "analysis_id": contracts.new_record_id("ran"),
        "reference_id": str(reference_id),
        "analysed_at": contracts.utc_now(),
        "findings": rows,
        "note": str(note),
        "derived_from": sorted({str(item) for row in rows for item in (row.get("inspection_ids") or [])}),
    }
    _transition(record, "ANALYSED", reason=f"{len(rows)} finding(s) generalised from inspection",
                updates={"analysis": analysis})
    return record


def mark_used(
    state: dict,
    reference_id: str,
    *,
    decision: str,
    principle: str,
    artifact_path: Path,
    artifact_anchor: str,
    requirement_id: str = "",
    direction_id: str = "",
    claim_kind: str = "",
) -> dict:
    """Record that a concrete design decision cites this reference.

    The decision must be anchored in a real artifact, so a reference mentioned in
    prose can never become ``USED``.
    """
    record = _require(state, reference_id)
    if str(record.get("state", "")) != "ANALYSED":
        raise ContractError("a reference must be ANALYSED before it can be USED")
    if not str(decision or "").strip() or not str(principle or "").strip():
        raise ContractError("a usage record needs the decision and the principle it rests on")
    if not str(artifact_anchor or "").strip():
        raise ContractError(
            "a usage record needs the artifact anchor it cites; without one, a reference mentioned in "
            "prose could become provenance"
        )
    artifact = evidence_artifact(
        Path(artifact_path), project=contracts.permitted_project_root(state, label="a usage artifact"),
    )
    text = Path(artifact["path"]).read_text(encoding="utf-8", errors="replace")
    if artifact_anchor not in text:
        raise ContractError(
            f"the usage anchor {artifact_anchor!r} does not occur in {Path(artifact_path).name}; "
            "a decision cannot claim an artifact it is not present in"
        )
    if claim_kind:
        normalised = str(claim_kind).strip().lower().replace("_", "-")
        if normalised not in CLAIM_KINDS:
            raise ContractError(f"unknown claim kind: {claim_kind!r}")
        allowed = set()
        for item in (record.get("inspections") or []):
            if isinstance(item, Mapping):
                allowed |= set(item.get("claim_kinds") or [])
        if normalised not in allowed:
            raise ContractError(
                f"the usage claims {normalised} but no inspection established it; "
                "a reference's evidence bounds the claims it can support"
            )
    usage = {
        "decided_at": contracts.utc_now(),
        "decision": str(decision),
        "principle": str(principle),
        "requirement_id": str(requirement_id),
        "direction_id": str(direction_id),
        "claim_kind": claim_kind,
        "artifact": artifact,
        "artifact_anchor": str(artifact_anchor),
    }
    _transition(record, "USED", reason="a design decision cites this reference", updates={"usage": usage})
    return record


# ------------------------------------------------------------- verification

def retrieval_dependencies(record: Mapping) -> dict:
    """The fingerprints a reference retrieval verification is bound to."""
    content = record.get("content") if isinstance(record.get("content"), Mapping) else {}
    return {
        "content-digest": str(content.get("sha256", "")),
        "locator": str(record.get("locator", "")),
        "retrieval-mode": str(content.get("retrieval_mode", "")),
        "revision": str(record.get("revision_hash", "")),
    }


def record_retrieval_verification(
    state: dict,
    reference_id: str,
    *,
    verification_execution: str,
    reproduced_artifact: Mapping,
    method: str,
) -> dict:
    """Independently reproduce a reference's retrieved content and record it.

    The verifier must be an engine-created execution, the re-produced artifact
    must be a real file the engine re-hashes, and its digest must equal the
    retrieved content digest. Only then is ``remote_origin_proven`` recorded, and
    even then the limitation is explicit: re-retrieval proves the source produced
    the same bytes again, not that the bytes are authoritative.
    """
    record = _require(state, reference_id)
    if str(record.get("state", "")) not in ("ACCESSIBLE", "INSPECTED", "ANALYSED"):
        raise ContractError(
            "a retrieval verification needs a reference whose content was actually retrieved "
            "(ACCESSIBLE, INSPECTED or ANALYSED)"
        )
    content = record.get("content") if isinstance(record.get("content"), Mapping) else {}
    expected = str(content.get("sha256", ""))
    if not expected:
        raise ContractError("the reference records no retrieved content digest to reproduce")
    from . import provenance, verification as verification_module

    verifier = provenance.require_engine_execution(
        state, verification_execution, label="a reference retrieval verification",
    )
    path_value = str((reproduced_artifact or {}).get("path", ""))
    if not path_value:
        raise ContractError("a retrieval verification needs the artifact the verifier retrieved")
    path = Path(path_value)
    if not path.is_file():
        raise ContractError(f"the re-retrieved artifact does not exist: {path}")
    actual = digest_file(path)
    if actual != expected:
        raise ContractError(
            "the re-retrieved content does not match the recorded retrieval; a mismatch is a finding, "
            "not a verification"
        )
    if str(method or "").strip() == "":
        raise ContractError("a retrieval verification needs the method that established it")
    verification_record = verification_module.create(
        state,
        subject=str(reference_id),
        subject_type="reference-retrieval",
        claim=f"the reference content {expected[:12]} is re-retrievable from its locator",
        level="INDEPENDENTLY_REPRODUCED",
        method=str(method),
        execution_id="",
        observed_anchor=f"reference:{reference_id}",
        verifier_execution_id=str(verifier.get("execution_id", "")),
        revision=str(record.get("revision_hash", "") or expected),
        evidence=[{
            "detail": "the reference record carries the retrieval digest this verification reproduces",
        }],
        observed_digest=expected,
        reproduced_artifact={"path": str(path.resolve()), "sha256": actual},
        dependencies=retrieval_dependencies(record),
        limitations=[
            "re-retrieval proves the same bytes were obtained again; it does not prove the source is "
            "authoritative, current or licensed for the intended use",
        ],
    )
    updated_content = dict(content)
    origin = dict(updated_content.get("origin") or {})
    origin.update({
        "remote_origin_proven": True,
        "verification_id": str(verification_record.get("verification_id", "")),
        "verification_execution": str(verifier.get("execution_id", "")),
    })
    updated_content["origin"] = origin
    candidate = dict(record)
    candidate["content"] = updated_content
    candidate["retrieval_verification"] = {
        "verification_id": str(verification_record.get("verification_id", "")),
        "verification_execution": str(verifier.get("execution_id", "")),
        "method": str(method),
        "digest": actual,
        "verified_at": contracts.utc_now(),
    }
    problems = contracts.reference_problems(candidate)
    if problems:
        raise ContractError("reference record would be malformed: " + "; ".join(problems))
    record.update(candidate)
    return record


def reference_currentness(
    state: dict,
    reference_id: str,
    *,
    current_digest: str = "",
    current_locator: str = "",
) -> dict:
    """Whether a reference's retrieval and its verification are still current.

    A local source is re-read when possible; an external source is compared
    against the supplied current digest. A changed digest or locator makes the
    retrieval stale; a missing verification record keeps the origin unproven.
    """
    from . import verification as verification_module

    record = _require(state, reference_id)
    content = record.get("content") if isinstance(record.get("content"), Mapping) else {}
    problems: list[str] = []
    stored = str(content.get("sha256", ""))
    if current_digest and stored and str(current_digest) != stored:
        problems.append("the reference content changed since it was retrieved")
    if current_locator and str(record.get("locator", "")) != str(current_locator):
        problems.append("the reference locator changed since it was retrieved")
    verification_record = None
    embedded = record.get("retrieval_verification") if isinstance(record.get("retrieval_verification"), Mapping) else {}
    if embedded:
        verification_record = verification_module.verification(state, str(embedded.get("verification_id", "")))
        if verification_record is None:
            problems.append("the recorded retrieval verification no longer exists")
        else:
            verdict = verification_module.freshness_of(
                verification_record,
                current={
                    **retrieval_dependencies(record),
                    **({"content-digest": str(current_digest)} if current_digest else {}),
                },
            )
            if verdict["state"] != "CURRENT":
                problems.append(
                    f"the retrieval verification is {verdict['state']}: " + "; ".join(verdict["problems"])
                )
    if problems:
        return {"state": "STALE", "problems": problems, "verified": bool(embedded)}
    if not stored:
        return {"state": "UNKNOWN", "problems": ["the reference records no retrieved content digest"], "verified": False}
    return {"state": "CURRENT", "problems": [], "verified": bool(embedded)}


# ------------------------------------------------------------- diversity

def diversity_notes(state: dict, *, reference_ids: Sequence[str] | None = None) -> dict:
    """Deterministic diversity facts for a reference set.

    Reports how many distinct sources and pattern families were analysed, which
    adopted mechanisms converge, and where they disagree. It deliberately makes
    no judgement: convergence is not evidence of correctness.
    """
    wanted = [str(item) for item in (reference_ids or [])]
    selected = [
        record for record in references(state)
        if (not wanted or str(record.get("reference_id")) in wanted)
        and str(record.get("state")) in ("ANALYSED", "USED")
    ]
    families: dict[str, int] = {}
    mechanisms: dict[str, list[str]] = {}
    for record in selected:
        analysis = record.get("analysis") if isinstance(record.get("analysis"), Mapping) else {}
        for finding in (analysis.get("findings") or []):
            if not isinstance(finding, Mapping):
                continue
            family = str(finding.get("dimension", ""))
            families[family] = families.get(family, 0) + 1
            if str(finding.get("decision", "")) == "adopted":
                mechanism = str(finding.get("mechanism", "")).strip()
                if mechanism:
                    mechanisms.setdefault(mechanism, []).append(str(record.get("source", "")))
    converged = {key: value for key, value in mechanisms.items() if len(set(value)) > 1}
    return {
        "analysed_references": len(selected),
        "distinct_sources": len({str(record.get("source", "")) for record in selected}),
        "dimensions": dict(sorted(families.items())),
        "convergent_mechanisms": dict(sorted(converged.items())),
        "convergence_note": (
            "convergence records that independent sources used the same mechanism; it is not "
            "evidence that the mechanism is correct for this project"
        ),
    }


def provenance_problems(state: dict) -> list[str]:
    """Cross-record provenance checks over the whole reference set."""
    problems: list[str] = []
    seen: set[str] = set()
    for record in references(state):
        reference_id = str(record.get("reference_id", ""))
        if reference_id in seen:
            problems.append(f"duplicate reference id: {reference_id}")
        seen.add(reference_id)
        problems.extend(contracts.reference_problems(record))
        analysis = record.get("analysis")
        if isinstance(analysis, Mapping):
            problems.extend(contracts.reference_analysis_problems(analysis))
            known = {str(item.get("inspection_id")) for item in (record.get("inspections") or []) if isinstance(item, Mapping)}
            for citation in (analysis.get("derived_from") or []):
                if str(citation) not in known:
                    problems.append(
                        f"reference {reference_id} analysis derives from an inspection it does not have: {citation}"
                    )
        content = record.get("content") if isinstance(record.get("content"), Mapping) else {}
        origin = content.get("origin") if isinstance(content.get("origin"), Mapping) else {}
        embedded = record.get("retrieval_verification") if isinstance(record.get("retrieval_verification"), Mapping) else {}
        if origin.get("remote_origin_proven") is True and not embedded:
            problems.append(
                f"reference {reference_id} claims a proven remote origin without a retrieval verification; "
                "a URL string is not retrieval proof"
            )
        if embedded:
            from . import verification as verification_module

            if verification_module.verification(state, str(embedded.get("verification_id", ""))) is None:
                problems.append(
                    f"reference {reference_id} cites a retrieval verification the run does not hold: "
                    f"{embedded.get('verification_id')}"
                )
    return list(dict.fromkeys(problems))


def summarise(state: dict) -> dict:
    """Deterministic reference-intelligence counters."""
    records = references(state)
    counts = {value.lower(): 0 for value in REFERENCE_STATES}
    inspections = {value.lower(): 0 for value in REFERENCE_INSPECTION_TYPES}
    analysed = 0
    used = 0
    for record in records:
        counts[str(record.get("state", "")).lower()] = counts.get(str(record.get("state", "")).lower(), 0) + 1
        for item in (record.get("inspections") or []):
            if isinstance(item, Mapping):
                key = str(item.get("type", "")).lower()
                inspections[key] = inspections.get(key, 0) + 1
        if isinstance(record.get("analysis"), Mapping):
            analysed += 1
        if isinstance(record.get("usage"), Mapping):
            used += 1
    return {
        "records": len(records),
        "states": counts,
        "found": counts.get("found", 0),
        "accessible": counts.get("accessible", 0),
        "inspected": counts.get("inspected", 0),
        "analysed": analysed,
        "used": used,
        "inaccessible": counts.get("inaccessible", 0),
        "inspection_types": inspections,
    }


def describe(record: Mapping) -> str:
    return (
        f"{record.get('reference_id')} {record.get('state')} "
        f"({record.get('source_type')} via {record.get('adapter')})"
    )


__all__ = [
    "CLAIM_KINDS",
    "INSPECTION_SUPPORTS",
    "INSPECTION_LABELS",
    "TRANSITIONS",
    "PROJECT_REFERENCE_DIRS",
    "ReferenceCandidate",
    "ReferenceAdapter",
    "UnavailableAdapter",
    "LocalReferenceAdapter",
    "ProjectDocumentAdapter",
    "FixtureReferenceAdapter",
    "ApprovedUrlAdapter",
    "OptionalProviderAdapter",
    "default_adapters",
    "capability_matrix",
    "require_source_type",
    "digest_bytes",
    "digest_file",
    "media_type",
    "evidence_artifact",
    "references",
    "reference",
    "register",
    "mark_accessible",
    "mark_inaccessible",
    "inspect",
    "analyse",
    "mark_used",
    "RETRIEVAL_MODES",
    "retrieval_dependencies",
    "record_retrieval_verification",
    "reference_currentness",
    "diversity_notes",
    "provenance_problems",
    "summarise",
    "describe",
]
