"""The getdesign.md adapter: the only module that knows what getdesign.md is (AR-220).

Everything getdesign-specific lives here. Nothing else in Ariadne parses a
getdesign.md URL, a slug shape or a page structure, so replacing this provider -
or losing access to it - is one module's problem rather than the design
workflow's.

What the live audit actually found (2026-10-03/04) - see
``docs/v2/2.2/03-GETDESIGN-MD-AUDIT.md`` for the full record:

===============================  ==========================================
``robots.txt``                   ``Allow: /``; only ``/vibecoder-kit-docs/``
                                 is disallowed. ``Sitemap: /sitemap.xml``.
Catalog size                     550+ entries, 764 sitemap URLs.
Entry URL shape                  ``https://getdesign.md/{slug}/design-md``
                                 where *slug* is host-like and **not** the
                                 brand name: ``linear.app``, ``x.ai``,
                                 ``mistral.ai``, ``cal`` (Cal.com),
                                 ``runwayml``, ``bmw-m``, ``dell-1996``.
Public on an entry page          title, description, brand summary, the
                                 analysis prose, the "best for" sentence,
                                 ``<link rel=canonical>``, JSON-LD
                                 ``CreativeWork``/``BreadcrumbList``, and an
                                 ``Installs`` counter.
Sign-in gated                    the **Download DESIGN.md** button, the
                                 Catalog Pass, private DESIGN.md requests,
                                 and both paid starter kits.
Public, unauthenticated          ``/design-md/{slug}/preview.html`` - a real
                                 rendered preview carrying the CSS custom
                                 properties.
Canonical raw DESIGN.md          the **open MIT-licensed GitHub repository**
                                 ``VoltAgent/awesome-design-md`` at
                                 ``design-md/{slug}/DESIGN.md``.
Official CLI                     ``npx getdesign@latest add {slug}``
                                 (Node; MIT; optional only).
===============================  ==========================================

Two of those facts shape the whole design:

**The site's Terms of Service, section 7, prohibit "automated means to scrape the
Service".** Ariadne therefore does not crawl getdesign.md. It performs
*targeted retrieval of specific public documents* - one catalog index the
operator points it at, and one file per selected candidate - through an
authorized fetch capability the operator must supply. No link-following, no
sitemap walking, no enumeration. :class:`GetDesignAdapter` refuses to run at all
without that capability, and its offline fixture mode is the default in tests.

**The raw DESIGN.md files are MIT-licensed and public in the source
repository.** That is the retrieval path AR-220 uses, because it is the path the
maintainers themselves publish for agents, it carries an explicit licence, and it
is not a scrape of the Service.

Search is deterministic text and category matching. No embeddings, no vector
database: a first pass that pretends to semantic similarity it does not have
would be a worse answer than honest lexical matching.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from .. import contracts
from ..contracts import ContractError
from . import normalize, safety

PROVIDER = "getdesign.md"
"""The provider identity recorded on every reference this adapter produces."""

CATALOG_HOST = "getdesign.md"
RAW_REPOSITORY = "VoltAgent/awesome-design-md"
RAW_REPOSITORY_LICENSE = "MIT"
RAW_REPOSITORY_URL = "https://github.com/VoltAgent/awesome-design-md"
RAW_BASE_URL = "https://raw.githubusercontent.com/VoltAgent/awesome-design-md"
CATALOG_BASE_URL = "https://getdesign.md"

SOURCE_KIND = "CURATED_DESIGN_ANALYSIS"
"""Every getdesign.md reference is a curated analysis, without exception.

This is the constant the whole curated-versus-first-party distinction turns on.
getdesign.md's own entry pages and Terms say so directly: "Independent analysis of
publicly observable patterns... Not affiliated with or endorsed by" the referenced
brand, and "they are not official design systems from the listed companies".

There is deliberately no code path in this module that can emit
``FIRST_PARTY_DESIGN_MD``. A description of Apple's design language is not
Apple's design system, and a third-party analysis that happens to be about a
famous brand does not become first-party by association.
"""

CATEGORIES = (
    "ai-llm-platforms", "developer-tools", "backend-database-devops",
    "productivity-saas", "design-creative-tools", "fintech-crypto",
    "ecommerce-retail", "media-consumer-tech", "automotive", "retro-web",
)
"""The catalog's own category vocabulary, used for deterministic matching.

Taken from the published collection's headings rather than invented, so a query
about "automotive" matches the entries the catalog itself files as automotive.
"""

INDUSTRY_TERMS: dict[str, tuple[str, ...]] = {
    "developer tooling": (
        "developer", "ide", "code editor", "terminal", "editor", "open source", "devops",
        "backend", "database", "deployment", "api", "documentation", "engineering", "toolchain",
    ),
    "premium finance dashboard": (
        "finance", "fintech", "crypto", "payment", "banking", "trading", "data-dense",
        "dashboard", "analytics", "institutional", "enterprise",
    ),
    "editorial brutalism": (
        "editorial", "magazine", "broadsheet", "retro", "1996", "2001", "y2k", "brutalist",
        "monochrome", "acid", "web magazine", "newspaper",
    ),
    "dark productivity app": (
        "dark", "productivity", "workspace", "project management", "scheduling", "slick",
        "minimal", "launcher", "email client", "automation", "crm",
    ),
    "cinematic automotive": (
        "automotive", "automobile", "cinematic", "supercar", "luxury", "electric vehicle",
        "chiaroscuro", "photography", "black", "motorsport",
    ),
    "dense technical interface": (
        "technical", "dense", "documentation", "infrastructure", "automation", "blueprint",
        "data", "console", "engineering", "monitoring", "analytics", "reference",
    ),
}
"""Query-intent vocabulary for the deterministic matcher.

These map the product-level questions Ariadne is asked onto the words the catalog
actually publishes in its titles and summaries. The mapping is explicit and
inspectable on purpose: a hidden semantic model would be impossible to audit, and
an unauditable relevance function is how a reference set quietly becomes
homogeneous.
"""

_STRONG_TERMS = frozenset({
    "developer", "terminal", "ide", "editor", "dashboard", "automotive", "editorial",
    "brutalist", "fintech", "crypto", "brutalism", "dense", "cinematic", "retro",
})
"""Terms whose presence in an entry is treated as a decisive relevance signal."""


@dataclass(frozen=True)
class GetDesignCandidate:
    """One catalog entry, before anything has been retrieved.

    A candidate is *not* a reference and carries no observations. This is the same
    discipline as AR-202D's ``ReferenceCandidate``: a search result snippet is
    never recorded as inspection.
    """

    slug: str
    brand: str
    summary: str
    category: str = ""
    entry_url: str = ""
    raw_url: str = ""
    best_for: str = ""
    score: float = 0.0
    matched: tuple[str, ...] = ()
    adapter: str = "getdesign-md"
    note: str = ""

    def as_record(self) -> dict:
        return {
            "slug": self.slug,
            "brand": self.brand,
            "summary": self.summary,
            "category": self.category,
            "entry_url": self.entry_url,
            "raw_url": self.raw_url,
            "best_for": self.best_for,
            "score": self.score,
            "matched": list(self.matched),
            "adapter": self.adapter,
            "note": self.note,
        }

    def source_identity(self) -> str:
        """Stable identity for change detection. Repo path, not a display name."""
        return f"{RAW_REPOSITORY}:{self.slug}"

    def title(self) -> str:
        return f"{self.brand} design system analysis" if self.brand else f"{self.slug} design analysis"


def build_index(entries: Sequence[Mapping]) -> list[GetDesignCandidate]:
    """Normalize a catalog index document into candidates.

    The index is accepted as plain rows rather than parsed out of HTML at this
    point. A live HTML catalog page is reduced to rows by
    :func:`parse_catalog_html`, which exists so the fragile part is one small,
    independently testable function instead of a selector buried in an adapter.
    """
    rows: list[GetDesignCandidate] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        slug = str(entry.get("slug", "")).strip()
        if not slug:
            continue
        if slug in seen:
            # A duplicate slug in the catalog is an ambiguity, not a second
            # candidate. Silently keeping the last one would make the index's
            # content depend on file order.
            raise ContractError(
                f"the getdesign.md catalog index declares slug {slug!r} twice; an ambiguous identifier is "
                "refused rather than resolved by order"
            )
        seen.add(slug)
        rows.append(GetDesignCandidate(
            slug=slug,
            brand=str(entry.get("brand", "")).strip(),
            summary=str(entry.get("summary", "")).strip(),
            category=str(entry.get("category", "")).strip().lower(),
            entry_url=entry_url(slug),
            raw_url=raw_url(slug),
            best_for=str(entry.get("best_for", "")).strip(),
        ))
    return rows


def entry_url(slug: str) -> str:
    return f"{CATALOG_BASE_URL}/{_safe_slug(slug)}/design-md"


def raw_url(slug: str) -> str:
    return f"{RAW_BASE_URL}/main/design-md/{_safe_slug(slug)}/DESIGN.md"


def preview_url(slug: str) -> str:
    return f"{CATALOG_BASE_URL}/design-md/{_safe_slug(slug)}/preview.html"


_SLUG_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]{0,80}[A-Za-z0-9])?$")
"""A slug may contain dots (``linear.app``) but never a separator.

Allowing ``/`` here would let a catalog index point the raw-URL builder at an
arbitrary path in another repository; keeping the character class to alphanumerics,
dot, dash and underscore means a hostile slug cannot escape the
``design-md/{slug}/DESIGN.md`` shape. Containment is re-checked at fetch time by
:func:`safety.require_fetchable_url`, so this is defence in depth rather than the
only check.
"""


def _safe_slug(slug: str) -> str:
    text = str(slug or "").strip()
    if not _SLUG_RE.match(text):
        raise ContractError(
            f"unsafe getdesign.md slug: {slug!r}; a slug must be a bare host-like identifier with no "
            "path separator, so a catalog entry cannot redirect retrieval elsewhere"
        )
    return text


# ------------------------------------------------------------- deterministic search


def search(
    index: Sequence[GetDesignCandidate],
    query: str,
    *,
    category: str = "",
    limit: int | None = None,
) -> list[GetDesignCandidate]:
    """Deterministic lexical search over the catalog index.

    Returns candidates ordered by descending score, ties broken by slug so the
    ordering is stable. The score is an *explainable* count of matched terms with a
    bonus for a strong term, not a learned similarity - every candidate carries the
    list of terms that matched, so a reviewer can see why it was returned.
    """
    safety.check_count(
        len(index), limit=contracts.MAX_DESIGN_REFERENCE_INDEX,
        label="getdesign.md catalog index size",
    )
    terms = _query_terms(query)
    wanted_category = str(category or "").strip().lower()
    scored: list[GetDesignCandidate] = []
    for candidate in index:
        if wanted_category and candidate.category != wanted_category:
            continue
        score, matched = _score(candidate, terms)
        if score <= 0.0:
            continue
        scored.append(GetDesignCandidate(
            slug=candidate.slug, brand=candidate.brand, summary=candidate.summary,
            category=candidate.category, entry_url=candidate.entry_url, raw_url=candidate.raw_url,
            best_for=candidate.best_for, score=score, matched=tuple(matched), adapter=candidate.adapter,
            note=candidate.note,
        ))
    scored.sort(key=lambda row: (-row.score, row.slug))
    cap = contracts.REFERENCE_BUDGET_DEFAULTS["candidate_retrieval"] if limit is None else int(limit)
    return scored[:cap]


def _query_terms(query: str) -> list[str]:
    """Expand a product-level question into catalog vocabulary.

    Expansion is a declared table, so the transformation from "what the user
    asked" to "what the catalog is searched for" is readable rather than learned:

    1. significant single words from the query survive as terms;
    2. every industry intent whose vocabulary *appears in the query* contributes
       its whole vocabulary, so "developer tooling" also retrieves entries that
       call themselves IDEs, terminals or deployment platforms.

    Step 2 is a substring test over the query text, not a word test. A
    multi-word catalog phrase such as ``"code editor"`` has to be able to light
    up the intent, and a per-word intersection would miss it.
    """
    text = " ".join(str(query or "").split()).lower()
    if not text:
        return []
    terms: set[str] = set()
    for word in re.split(r"[^a-z0-9+.-]+", text):
        if word and word not in _STOPWORDS:
            terms.add(word)
    for vocabulary in INDUSTRY_TERMS.values():
        if any(phrase in text for phrase in vocabulary):
            terms.update(vocabulary)
    return sorted(terms)


_STOPWORDS = frozenset({
    "a", "an", "the", "for", "with", "and", "or", "of", "to", "in", "on", "it", "is",
    "be", "that", "this", "should", "not", "but", "like", "make", "build", "design",
    "create", "serious", "precise", "calm", "generic", "dashboard", "want", "need",
})
"""Words that carry no retrieval signal in a design-intent query."""


def _score(candidate: GetDesignCandidate, terms: Sequence[str]) -> tuple[float, list[str]]:
    if not terms:
        return 0.0, []
    brand = candidate.brand.lower()
    summary = candidate.summary.lower()
    best_for = candidate.best_for.lower()
    category = candidate.category.lower()
    score = 0.0
    matched: list[str] = []
    for term in terms:
        hit = False
        if term == brand:
            score += 6.0
            hit = True
        elif term and term in brand:
            score += 4.0
            hit = True
        elif term and term in summary:
            score += 2.0
            hit = True
        elif term and term in best_for:
            score += 1.5
            hit = True
        elif term and term in category:
            score += 1.0
            hit = True
        if hit:
            matched.append(term)
            if term in _STRONG_TERMS:
                score += 2.0
    if not matched:
        return 0.0, []
    # A slug that equals the brand lowercased is a naming coincidence, not a match.
    if candidate.slug.lower() in brand and brand != candidate.slug.lower():
        score -= 1.0
    return max(score, 0.0), matched


# ------------------------------------------------------------------- HTML parsing

_LINK_RE = re.compile(r'<a\b[^>]*href="/(?P<slug>[A-Za-z0-9._-]{1,80})/design-md"[^>]*>(?P<inner>.*?)</a>',
                      re.IGNORECASE | re.DOTALL)
_H1_RE = re.compile(r"<h1\b[^>]*>(?P<inner>.*?)</h1>", re.IGNORECASE | re.DOTALL)
_META_DESCRIPTION_RE = re.compile(r'<meta\s+name="description"\s+content="(?P<value>[^"]*)"', re.IGNORECASE)
_CANONICAL_RE = re.compile(r'<link\s+rel="canonical"\s+href="(?P<value>[^"]*)"', re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(value: str) -> str:
    return " ".join(_TAG_RE.sub(" ", str(value or "")).split())


def parse_catalog_html(html: str, *, limit: int | None = None) -> list[dict]:
    """Reduce a rendered catalog page to index rows.

    Three independent signals are used, so no single CSS selector is load-bearing:
    the ``<h1>`` heading for the catalog's own framing, ``<meta name=description>``
    for the page summary, and every ``<a href="/{slug}/design-md">`` semantic link
    for the entries. A page that renders its catalog differently produces fewer
    rows rather than an exception, and the caller sees a smaller index.
    """
    if not isinstance(html, str):
        raise ContractError("catalog HTML must be supplied as text")
    safety.check_document_size(
        html, limit=contracts.MAX_DESIGN_REFERENCE_BYTES, label="getdesign.md catalog page"
    )
    rows: list[dict] = []
    seen: set[str] = set()
    for match in _LINK_RE.finditer(html):
        slug = match.group("slug")
        if slug in seen or slug in ("", "design-md"):
            continue
        seen.add(slug)
        rows.append({"slug": slug, "brand": "", "summary": ""})
    description = _META_DESCRIPTION_RE.search(html)
    if description:
        summary = strip_tags(description.group("value"))
        for row in rows:
            row["summary"] = summary if len(rows) == 1 else ""
    heading = _H1_RE.search(html)
    if heading and len(rows) == 1:
        title = strip_tags(heading.group("inner"))
        rows[0]["brand"] = re.sub(r"^Design System Analysis:\s*", "", title, flags=re.IGNORECASE)
    cap = contracts.REFERENCE_BUDGET_DEFAULTS["candidate_retrieval"] if limit is None else int(limit)
    return rows[:cap]


def parse_entry_html(html: str, *, slug: str) -> dict:
    """Read one public entry page into structured metadata.

    Returns ``{}`` plus ``problems`` rather than raising when the page shape is
    unfamiliar, because a catalog that changes its markup should degrade to "less
    metadata observed", not to a crashed design workflow.
    """
    safety.check_document_size(
        html, limit=contracts.MAX_DESIGN_REFERENCE_BYTES, label=f"getdesign.md entry page for {slug}"
    )
    problems: list[str] = []
    title = ""
    heading = _H1_RE.search(html)
    if heading:
        title = re.sub(
            r"^Design System Analysis:\s*", "", strip_tags(heading.group("inner")), flags=re.IGNORECASE
        )
    else:
        problems.append("entry page exposes no <h1>; brand is unknown")
    description = _META_DESCRIPTION_RE.search(html)
    summary = strip_tags(description.group("value")) if description else ""
    if not summary:
        problems.append("entry page exposes no meta description")
    canonical = _CANONICAL_RE.search(html)
    if canonical and f"/{slug}/design-md" not in canonical.group("value"):
        problems.append(
            f"entry page canonical {canonical.group('value')!r} does not name /{slug}/design-md; "
            "the page may not be the entry it claims to be"
        )
    gated = bool(re.search(r"Download\s+DESIGN\.md", html, re.IGNORECASE))
    disclaimer = _DISCLAIMER_RE.search(html)
    result = {
        "slug": slug,
        "brand": title,
        "summary": summary,
        "entry_url": entry_url(slug),
        "canonical": canonical.group("value") if canonical else "",
        "raw_document_download_gated": gated,
        "first_party_disclaimer": bool(disclaimer),
        "disclaimer_text": strip_tags(disclaimer.group(0))[:300] if disclaimer else "",
        "preview_url": preview_url(slug),
        "best_for": _best_for(html),
    }
    result["problems"] = problems
    return result


_DISCLAIMER_RE = re.compile(
    r"Independent analysis of publicly observable patterns[^<]*", re.IGNORECASE
)
_BEST_FOR_RE = re.compile(r"You will get the best results in\s+(?P<value>[^<.]+)", re.IGNORECASE)


def _best_for(html: str) -> str:
    match = _BEST_FOR_RE.search(html)
    return " ".join(match.group("value").split())[:300] if match else ""


# ------------------------------------------------------------------- the adapter


@dataclass
class GetDesignAdapter:
    """Read-only getdesign.md reference source.

    Two modes, and the default is the offline one:

    ``offline``  serves a recorded catalog index and a frozen corpus of retrieved
                 documents. Every regression test runs here. Nothing is fetched,
                 so nothing about a test result depends on a third party's uptime.
    ``live``     requires an operator-supplied authorized fetch capability. Every
                 request is a *targeted* GET of one named URL: there is no
                 sitemap walking, no link following and no enumeration.

    The adapter is refused outright - not degraded - when asked to run live with
    no fetch capability, because silently returning zero rows would be
    indistinguishable from "this catalog has no entry for your query".
    """

    index: Sequence[Mapping] = ()
    corpus: Mapping[str, bytes] = field(default_factory=dict)
    fetcher: object = None
    allowlist: Sequence[str] = (RAW_BASE_URL, CATALOG_BASE_URL)
    max_requests: int = 8
    requests_made: int = 0
    unavailable_note: str = ""
    """Why this adapter is unavailable. Separate from ``unavailable_reason()``.

    Named differently because the AR-202D adapter contract exposes
    ``unavailable_reason()`` as a *method*; a dataclass field of the same name
    would shadow it, and the capability record would raise instead of reporting.
    """

    id = "getdesign-md"
    source_type = "official-api"
    kind = "reference"
    description = "getdesign.md curated design-system analyses (MIT-licensed corpus)"

    def capabilities(self) -> tuple[str, ...]:
        return ("discover", "retrieve_metadata", "retrieve_content", "inspect_visual")

    def enabled(self) -> bool:
        """Whether this adapter can actually return reference bytes.

        Requires a retrieval path, not just an index. An index with neither a
        frozen corpus nor an authorized fetch capability can enumerate candidates
        but cannot inspect any of them, and reporting that as ``enabled`` would
        make a live run silently retrieve nothing.
        """
        return bool(self.index) and (self.fetcher is not None or bool(self.corpus))

    def unavailable_reason(self) -> str:
        if self.enabled():
            return ""
        return self.unavailable_note or (
            "no getdesign.md catalog index is configured, or no retrieval path (frozen corpus or "
            "authorized fetch capability); Ariadne does not crawl getdesign.md, so an index must be "
            "supplied explicitly or the capability is honestly unavailable"
        )

    def capability_record(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "source_type": self.source_type,
            "description": self.description,
            "capabilities": list(self.capabilities()),
            "enabled": bool(self.enabled()),
            "unavailable_reason": self.unavailable_reason(),
            "mode": "live" if self.fetcher is not None else "offline",
            "retrieval_policy": RETRIEVAL_POLICY,
            "source_kind": SOURCE_KIND,
            "license": RAW_REPOSITORY_LICENSE,
            "repository": RAW_REPOSITORY,
        }

    # ------------------------------------------------------------- searching

    def candidates(self) -> list[GetDesignCandidate]:
        return build_index(self.index)

    def discover(self, query: Mapping) -> list[GetDesignCandidate]:
        value = query or {}
        return search(
            self.candidates(),
            str(value.get("query", "") or ""),
            category=str(value.get("category", "") or ""),
            limit=value.get("limit"),
        )

    # ------------------------------------------------------------- retrieval

    def fetch_document(self, candidate: GetDesignCandidate) -> bytes:
        """Return the raw DESIGN.md bytes for *candidate*.

        Offline: from the frozen corpus, keyed by slug. Live: one targeted GET of
        the repository's raw path, behind an operator-supplied fetch capability,
        under the request budget.
        """
        slug = _safe_slug(candidate.slug)
        if self.fetcher is None:
            body = self.corpus.get(slug)
            if body is None:
                raise ContractError(
                    f"no recorded getdesign.md document for {slug!r}; the offline corpus is the only "
                    "evidence available and it does not contain this entry"
                )
            return bytes(body)
        if self.requests_made >= int(self.max_requests):
            raise ContractError(
                f"getdesign.md retrieval request budget of {self.max_requests} is exhausted; "
                "reference research stops rather than continuing to fetch"
            )
        url = safety.require_fetchable_url(raw_url(slug), label="getdesign.md raw document")
        # At least one allowlist prefix must match. An earlier version raised
        # inside the loop unless *every* prefix matched, which inverted the check
        # and refused the provider's own documented host.
        if not any(url.startswith(str(prefix)) for prefix in self.allowlist):
            raise ContractError(
                f"getdesign.md retrieval target {url!r} is outside the configured allowlist "
                + repr([str(prefix) for prefix in self.allowlist])
            )
        self.requests_made += 1
        payload = self.fetcher(url)  # type: ignore[operator]
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        if not isinstance(payload, (bytes, bytearray)):
            raise ContractError("an authorized fetcher must return the retrieved bytes")
        return bytes(payload)

    def fetch_entry_metadata(self, candidate: GetDesignCandidate) -> dict:
        """Public catalog metadata for *candidate*, when a fetch capability exists."""
        if self.fetcher is None:
            return {"available": False, "reason": "offline mode performs no network retrieval"}
        if self.requests_made >= int(self.max_requests):
            return {"available": False, "reason": "request budget exhausted"}
        url = safety.require_fetchable_url(entry_url(candidate.slug), label="getdesign.md entry page")
        self.requests_made += 1
        payload = self.fetcher(url)  # type: ignore[operator]
        return parse_entry_html(
            payload.decode("utf-8", errors="replace") if isinstance(payload, (bytes, bytearray))
            else str(payload),
            slug=candidate.slug,
        )

    # --------------------------------------------------------- normalisation

    def normalize(
        self,
        candidate: GetDesignCandidate,
        *,
        retrieved_at: str,
        entry_metadata: Mapping | None = None,
    ) -> dict:
        """``fetch -> normalize`` into one provider-neutral ``DesignReference``.

        The ``source_kind`` is the constant :data:`SOURCE_KIND`. No caller can
        pass a different kind, because that is precisely the mistake this layer
        exists to make impossible.
        """
        body = self.fetch_document(candidate)
        limitations: list[str] = []
        license_status = RAW_REPOSITORY_LICENSE
        attribution = f"getdesign.md curated analysis via {RAW_REPOSITORY} ({RAW_REPOSITORY_LICENSE})"
        metadata = dict(entry_metadata or {})
        if metadata:
            if metadata.get("raw_document_download_gated"):
                limitations.append(
                    "the catalog's own DESIGN.md download is sign-in gated; the document read here comes "
                    "from the maintainers' public MIT-licensed repository instead"
                )
            if metadata.get("first_party_disclaimer") is False:
                limitations.append(
                    "the entry page carried no first-party disclaimer, so its provenance could not be "
                    "confirmed from the page itself"
                )
        record = normalize.normalize_reference(
            source_kind=SOURCE_KIND,
            source_provider=PROVIDER,
            source_identity=candidate.source_identity(),
            source_uri=raw_url(candidate.slug),
            retrieved_at=str(retrieved_at),
            content=body,
            title=candidate.title(),
            brand=candidate.brand,
            product=str(metadata.get("brand", "") or candidate.brand),
            surface="website",
            reference_type="design-system-analysis",
            evidence_level="CURATED_ANALYSIS",
            access_mode="PUBLIC",
            license_status=license_status,
            attribution=attribution,
            source_revision=f"{RAW_REPOSITORY}@main",
            limitations=limitations,
            applicable_requirements=(
                [str(metadata["best_for"])] if metadata.get("best_for") else []
            ),
        )
        record["candidate"] = candidate.as_record()
        record["design_document"]["bytes"] = len(body)
        record["retrieved_bytes"] = len(body)
        if metadata:
            record["catalog_metadata"] = metadata
        return record

    # -------------------------------------------------------------- fixtures

    @classmethod
    def from_corpus(cls, directory: Path) -> "GetDesignAdapter":
        """Build an offline adapter from a recorded fixture directory.

        Expects ``catalog.json`` plus one ``{slug}.md`` per frozen document. This
        is how a live retrieval is turned into a permanent regression fixture: run
        the retrieval once, record the bytes, and every later test uses the
        recording.
        """
        base = Path(directory)
        catalog_path = base / "catalog.json"
        if not catalog_path.is_file():
            raise ContractError(f"getdesign.md fixture directory has no catalog.json: {base}")
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        corpus: dict[str, bytes] = {}
        for slug in catalog.get("slugs", []) or []:
            path = base / f"{_safe_slug(slug)}.md"
            if not path.is_file():
                raise ContractError(f"getdesign.md fixture corpus is missing {path.name}")
            corpus[_safe_slug(slug)] = path.read_bytes()
        return cls(index=catalog.get("entries", []) or [], corpus=corpus)


RETRIEVAL_POLICY = (
    "targeted single-file HTTPS retrieval only; no crawling, no sitemap walking, no link following, "
    "no enumeration, no authenticated endpoints, no paywall or entitlement bypass; bounded request "
    "budget; every retrieval must carry an operator-supplied authorized fetch capability"
)
"""The declared retrieval policy, recorded on the adapter's capability record.

Recorded rather than merely documented because it is the thing an operator has to
agree to before supplying a fetch capability. getdesign.md's Terms of Service
prohibit automated scraping of the Service, so the honest integration is narrow
retrieval of public documents - and the policy says so where it can be audited.
"""

ADAPTER_ID = "getdesign-md"


def default_adapter(fixture_root: Path | None = None) -> GetDesignAdapter:
    """The shipped getdesign.md adapter: offline and fixture-backed by default."""
    if fixture_root is not None and Path(fixture_root).is_dir():
        return GetDesignAdapter.from_corpus(Path(fixture_root))
    return GetDesignAdapter()


__all__ = [
    "ADAPTER_ID",
    "CATEGORIES",
    "CATALOG_BASE_URL",
    "INDUSTRY_TERMS",
    "PROVIDER",
    "RAW_BASE_URL",
    "RAW_REPOSITORY",
    "RAW_REPOSITORY_LICENSE",
    "RAW_REPOSITORY_URL",
    "RETRIEVAL_POLICY",
    "SOURCE_KIND",
    "GetDesignAdapter",
    "GetDesignCandidate",
    "build_index",
    "default_adapter",
    "entry_url",
    "parse_catalog_html",
    "parse_entry_html",
    "preview_url",
    "raw_url",
    "search",
]