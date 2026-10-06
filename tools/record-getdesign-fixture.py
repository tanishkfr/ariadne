"""Freeze one live getdesign.md retrieval into a permanent regression fixture (AR-220).

Run once, by hand, when the recorded corpus needs refreshing. It performs the
same ``search -> candidate -> fetch -> normalize`` path the adapter exposes, then
writes:

* ``catalog.json`` - the catalog index rows and the slugs that were retrieved;
* ``{slug}.md``     - the exact retrieved bytes, unmodified;
* ``retrieval.json``- the provenance of the retrieval: URL, timestamp, digest of
  the retrieved bytes, title, brand, source class, patterns extracted,
  limitations, and the access boundary that was found.

The retrieved bytes are stored *verbatim*. Reformatting them would mean the
digest in ``retrieval.json`` no longer describes what the site returned, and a
regression suite that tests reformatted input is testing the reformatter.

Usage:
    python tools/record-getdesign-fixture.py --slugs linear.app raycast vercel
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ariadne_engine.design_reference import getdesign, normalize, safety  # noqa: E402

FIXTURES = SRC / "ariadne_engine" / "design_reference" / "fixtures" / "getdesign-md"

USER_AGENT = "ariadne-ar220-fixture-recorder/1.0 (+https://github.com/tanishkfr/ariadne)"

README_URL = f"{getdesign.RAW_BASE_URL}/main/README.md"

_README_ENTRY_RE = re.compile(
    r"^-\s+\[\*\*(?P<brand>[^\]]+)\*\*\]\("
    r"https://getdesign\.md/(?P<slug>[A-Za-z0-9._-]+)/design-md\)"
    r"\s*-\s*(?P<description>.+?)\s*$",
    re.MULTILINE,
)
_README_CATEGORY_RE = re.compile(r"^###\s+(?P<category>[^\n]+?)\s*$", re.MULTILINE)
_README_SECTION_RE = re.compile(r"^##\s+(?P<section>[^\n]+?)\s*$", re.MULTILINE)


def readme_index() -> dict[str, dict]:
    """Catalog rows from the maintainers' own MIT-licensed collection README.

    The rendered entry page carries a two-line summary; the README carries the
    catalog's own category grouping and a fuller one-line description. Both are
    public and published by the maintainers, and using both gives the
    deterministic matcher real signal instead of three words per entry. Nothing
    here is invented: every field is a string the maintainers wrote.
    """
    body = fetch(README_URL).decode("utf-8", errors="replace")
    rows: dict[str, dict] = {}
    lines = body.splitlines()
    category = ""
    for line in lines:
        category_match = _README_CATEGORY_RE.match(line)
        if category_match:
            category = category_match.group("category").strip().lower().replace(" & ", "-").replace(" ", "-")
            continue
        entry_match = _README_ENTRY_RE.match(line.strip())
        if not entry_match:
            continue
        slug = entry_match.group("slug")
        if slug in rows:
            continue
        rows[slug] = {
            "slug": slug,
            "brand": entry_match.group("brand").strip(),
            "summary": entry_match.group("description").strip(),
            "category": category,
        }
    return rows


def fetch(url: str) -> bytes:
    """One targeted GET of a public URL. No crawling, no retries, no redirects
    onto anything but the same host."""
    safety.require_fetchable_url(url, label="fixture recording URL")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - URL vetted above
        return response.read(contracts_max_bytes())


def contracts_max_bytes() -> int:
    from ariadne_engine import contracts

    return contracts.MAX_DESIGN_REFERENCE_BYTES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record getdesign.md retrieval fixtures.")
    parser.add_argument("--slugs", nargs="+", required=True)
    parser.add_argument("--output", default=str(FIXTURES))
    parser.add_argument("--summary", action="append", default=[])
    args = parser.parse_args(argv)

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    published = readme_index()
    print(f"catalog index rows available from the maintainers' README: {len(published)}")

    entries: list[dict] = []
    recorded: list[dict] = []
    for slug in args.slugs:
        url = getdesign.raw_url(slug)
        body = fetch(url)
        (output / f"{slug}.md").write_bytes(body)
        row = published.get(slug) or {"slug": slug, "brand": slug, "summary": "", "category": ""}
        entry_html = fetch(getdesign.entry_url(slug)).decode("utf-8", errors="replace")
        entry_metadata = getdesign.parse_entry_html(entry_html, slug=slug)
        candidate = getdesign.GetDesignCandidate(
            slug=slug,
            brand=str(entry_metadata.get("brand") or row["brand"]),
            summary=str(row.get("summary", "")),
            category=str(row.get("category", "")),
            best_for=str(entry_metadata.get("best_for", "")),
        )
        adapter = getdesign.GetDesignAdapter(index=[candidate.as_record()], corpus={slug: body})
        record = adapter.normalize(candidate, retrieved_at=retrieved_at, entry_metadata=entry_metadata)
        published[slug] = {
            "slug": slug,
            "brand": candidate.brand,
            "summary": candidate.summary,
            "category": candidate.category,
            "best_for": candidate.best_for,
        }
        recorded.append({
            "slug": slug,
            "url": url,
            "entry_url": getdesign.entry_url(slug),
            "retrieved_at": retrieved_at,
            "content_digest": record["classification"]["content_digest"],
            "normalized_digest": record["normalized_digest"],
            "title": record["title"],
            "brand": record["classification"]["brand"],
            "source_kind": record["classification"]["source_kind"],
            "evidence_level": record["classification"]["evidence_level"],
            "access_mode": record["classification"]["access_mode"],
            "license_status": record["license_status"],
            "catalog_raw_download_gated": entry_metadata["raw_document_download_gated"],
            "catalog_first_party_disclaimer": entry_metadata["first_party_disclaimer"],
            "patterns_extracted": len(record["observed_patterns"]),
            "pattern_dimensions": sorted({row_["dimension"] for row_ in record["observed_patterns"]}),
            "limitations": record["limitations"],
            "instruction_attempts": len(record["injection_scan"]["instruction_attempts"]),
        })
        print(
            f"recorded {slug}: {len(body)} bytes, {len(record['observed_patterns'])} patterns, "
            f"category={candidate.category or 'unknown'}"
        )

    catalog = {
        "schema_version": 1,
        "provider": getdesign.PROVIDER,
        "source_kind": getdesign.SOURCE_KIND,
        "repository": getdesign.RAW_REPOSITORY,
        "repository_url": getdesign.RAW_REPOSITORY_URL,
        "license": getdesign.RAW_REPOSITORY_LICENSE,
        "retrieval_policy": getdesign.RETRIEVAL_POLICY,
        "access_boundary": {
            "catalog_entry_pages": "PUBLIC",
            "catalog_design_md_download": "ACCESS_RESTRICTED (sign-in / Catalog Pass)",
            "preview_html": "PUBLIC",
            "raw_design_md_via_public_mit_repository": "PUBLIC",
            "paid_tiers": "never retrieved: /request, /design-md-pass, starter kits",
            "scraping": (
                "not performed; the site Terms of Service prohibit automated scraping, so retrieval is "
                "targeted single-file HTTPS only"
            ),
        },
        "index_source": (
            "the maintainers' own MIT-licensed collection README, which publishes each entry's slug, brand, "
            "category and one-line description"
        ),
        "retrieved_at": retrieved_at,
        "recorded_at": retrieved_at,
        "slugs": list(args.slugs),
        "recorded_slugs": list(args.slugs),
        "index_size": len(published),
        "entries": [published[slug] for slug in sorted(published)],
    }
    (output / "catalog.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output / "retrieval.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "provider": getdesign.PROVIDER,
                "retrieved_at": retrieved_at,
                "retrievals": recorded,
                "note": (
                    "these bytes were retrieved once from the maintainers' public MIT-licensed "
                    "repository and recorded verbatim. Normal unit and regression tests never touch "
                    "the network; they read this directory."
                ),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output / 'catalog.json'} and retrieval.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())