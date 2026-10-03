# 03 — getdesign.md Audit (AR-220)

Live audit performed **2026-10-03 / 2026-10-04**. Everything below was observed,
not assumed. Where the AR-220 brief's expectation differed from reality, reality is
recorded.

## Integration classification

```text
Integration classification : CURATED_DESIGN_ANALYSIS (constant, not a parameter)
Access model               : public catalog browsing; DESIGN.md download is sign-in gated
Retrieval permitted        : targeted single-file HTTPS, authorized fetch capability only
Crawling permitted         : NO — the site's Terms of Service prohibit automated scraping
Raw document source used   : the maintainers' public MIT-licensed GitHub repository
Runtime dependency         : none. No Node, no npm, no package installed.
```

## Site facts

| Fact | Observed value |
|------|----------------|
| Site | `https://getdesign.md/` |
| Operator | the VoltAgent team |
| `robots.txt` | `User-agent: *`, `Allow: /`, `Disallow: /vibecoder-kit-docs/`, `Sitemap: https://getdesign.md/sitemap.xml` |
| Catalog size | **550+** entries advertised in the site's own navigation |
| `sitemap.xml` | HTTP 200, 104 225 bytes, **764** `<loc>` entries |
| Entry URL shape | `https://getdesign.md/{slug}/design-md` |
| Entry page title | `Design System Analysis: {Brand}` |
| Maintained by | VoltAgent; collection repo `VoltAgent/awesome-design-md` |

> The AR-220 brief expected "300+ entries". The live site advertised **550+** and
> the sitemap listed 764 URLs. The recorded figure is the live one.

### Slugs are host-like, not brand names

This is the single most likely integration mistake, and it is why the adapter never
derives a URL from a brand string:

| Brand | Slug |
|-------|------|
| Linear | `linear.app` |
| xAI | `x.ai` |
| Mistral AI | `mistral.ai` |
| Together AI | `together.ai` |
| OpenCode AI | `opencode.ai` |
| Cal.com | `cal` |
| Runway | `runwayml` |
| BMW M | `bmw-m` |
| Dell (1996) | `dell-1996` |

`GetDesignCandidate.slug` is the **only** input to the URL builders, and
`getdesign._safe_slug` refuses anything containing a path separator. A hostile
catalog index cannot redirect retrieval to another host or another repository path.

## Catalog behaviour

`https://getdesign.md/` is a search-and-browse landing page. Publicly visible on
it: brand name, a one-line summary ("Linear — Project management. Ultra-minimal,
precise, purple accent."), tabs for Installs and Bookmarked, and links to
`/request`, `/design-md`, `/design-md-pass`, `/backgrounds`, `/video-template`.

The catalogue index Ariadne searches is **not** parsed from that rendered page. It
is taken from the maintainers' own collection README in the MIT-licensed
repository, which publishes each entry's slug, brand, category and a fuller
one-line description. 73 rows were recorded.

Rationale: the rendered page carries roughly ten words per entry, which is not
enough signal for honest lexical matching. The README is published by the same
maintainers, under the same MIT licence, and carries strictly more information. Both
are public and neither is invented.

`getdesign.parse_catalog_html` exists for the rendered page anyway, using three
independent signals (`<h1>`, `<meta name=description>`, and semantic
`<a href="/{slug}/design-md">` links) so that no single CSS selector is
load-bearing. A page that renders differently yields fewer rows rather than an
exception.

## Reference page format

An entry page at `https://getdesign.md/{slug}/design-md` is server-rendered HTML.
Publicly observable, and parsed by `getdesign.parse_entry_html`:

| Signal | Present | Used for |
|--------|---------|----------|
| `<title>` / `<h1>` | yes | brand |
| `<meta name="description">` | yes | summary |
| `<link rel="canonical">` | yes | identity check |
| JSON-LD `CreativeWork` + `BreadcrumbList` | yes | identity corroboration |
| Analysis prose ("*Linear takes project management as its base, then sharpens it…*") | yes | applicability |
| "You will get the best results in …" sentence | on some entries | `best_for` |
| `Installs` / `Bookmarked` counters | yes | popularity (not used as a quality signal) |
| **First-party disclaimer** | **yes, on every audited entry** | provenance |
| **"Download DESIGN.md" button** | **yes, sign-in gated** | access boundary |

The disclaimer, verbatim from a live entry page:

> *"Independent analysis of publicly observable patterns, curated as a starting point
> for inspiration. Not affiliated with or endorsed by Linear; Linear and its logo are
> trademarks of their respective owner."*

This is the site's own statement of the curated/first-party distinction, and it is
why `getdesign.SOURCE_KIND` is a module constant.

## Public / private boundary

Probed and recorded, not guessed:

| Surface | Result |
|---------|--------|
| `/{slug}/design-md` entry page | **200**, public |
| `/design-md/{slug}/preview.html` | **200**, public, unauthenticated, 37 822 bytes for `linear.app`, carrying real CSS custom properties (`--primary: #5e6ad2`, `--canvas: #010102`, `--hairline: #23252a`, …) |
| `/{slug}/design-md.md` | 404 |
| `/{slug}/DESIGN.md` | 404 |
| `/{slug}/design-md/raw` | 404 |
| `/{slug}/design-md/download` | 404 |
| **Download DESIGN.md (button)** | **sign-in gated — Catalog Pass / paid** |
| `/request` (Private DESIGN.md) | paid |
| `/design-md-pass` (Catalog Pass) | paid |
| Website / Mobile starter kits | paid |

**Conclusion: the raw DESIGN.md is not publicly downloadable from the catalog.**
The download control requires an account and, in practice, the Catalog Pass. Any
integration that reports otherwise is describing an entitlement it does not have.

Ariadne therefore records `ACCESS_RESTRICTED` for that surface and reads the
documents from elsewhere.

## Raw DESIGN.md availability — the usable path

The raw documents are published by the maintainers in an open repository:

```text
repository : VoltAgent/awesome-design-md
licence    : MIT
url        : https://github.com/VoltAgent/awesome-design-md
path       : design-md/{slug}/DESIGN.md
raw        : https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/{slug}/DESIGN.md
```

Every entry page also documents the maintainers' own machine path:

```bash
npx getdesign@latest add linear.app
```

So there is a sanctioned agent path, and Ariadne uses the repository half of it:
no npm install, no files written into a user project, no Node dependency, and no
scraping of the Service.

## Two roles, two sources, one provider name

A reader can reasonably come away from this audit believing the Service serves the
bytes. It does not, and the distinction is the whole retrieval design.

| | getdesign.md (the Service) | VoltAgent/awesome-design-md (the repository) |
|---|---|---|
| Role | **editorial + provenance** | **retrieval** |
| Publishes | the catalogue UI, the per-entry analysis page, the curated prose, the first-party disclaimer, popularity counters, `best_for` | the catalogue index itself (collection README, 73 rows) and every raw `DESIGN.md` |
| Access | public pages; the raw download is sign-in gated | public, MIT-licensed, no account |
| Bytes Ariadne actually read | **0** | **107 634**, across 5 documents |

So the split is:

1. **Discovery** is nominally the Service's catalogue, but the index Ariadne searches
   is the maintainers' README, because the rendered page carries too few words per
   entry to match honestly. Same maintainers, same licence, strictly more signal.
2. **Content** comes only from the repository. The Service cannot supply it at any
   price Ariadne is willing to pay — that surface is `ACCESS_RESTRICTED`.
3. **`PROVIDER = "getdesign.md"`** is therefore an editorial identity, not a transport
   host. It names *whose analysis these are*, and it is the honest name for a
   collection VoltAgent curates and publishes. The `source_uri` on every normalised
   record points at the repository path the bytes came from, so a record never claims
   a provenance it does not have.
4. In the recorded offline mode the Service contributes nothing at all. Every
   `CURATED_DESIGN_ANALYSIS` in AR-220's fixtures was retrieved from the repository,
   and the Service was consulted once by hand during the audit.

## Terms and robots

**`robots.txt`** allows the catalog (`Allow: /`, one disallowed documentation
directory). So crawling would be *permitted* by robots.

**Terms of Service, section 7 (Acceptable Use)** prohibits:

> *"Attempt to circumvent payment, access controls, or rate limits, or use automated
> means to scrape the Service."*

robots permitting a path and the Terms forbidding automated scraping of it are both
true, and the Terms are the tighter constraint. Ariadne resolves the conflict the
conservative way, and records the resolution:

- **no crawling**, no sitemap walking, no link following, no enumeration;
- **targeted single-file retrieval only**, of a URL an operator selected;
- **an operator-supplied authorized fetch capability is required** — the adapter
  refuses to run without one rather than degrading to zero rows;
- a bounded request budget;
- **no authenticated endpoints** and no paywall or entitlement bypass, ever.

The policy is stored on the adapter's capability record
(`getdesign.RETRIEVAL_POLICY`) so an operator reads what they are agreeing to
before supplying a fetch capability.

## Terms section 8 — the copyright boundary

> *"Each DESIGN.md is an independent editorial analysis of publicly observable
> visual patterns; it is not a copy of, derivative work from, or substitute for any
> third party's design system documentation."*

This aligns exactly with AR-220's design intent: extract principles, synthesise an
original direction, do not build a "copy brand exactly" engine. Ariadne's own
standing `reuse_constraints` say the same thing independently.

## The recorded retrieval

`tools/record-getdesign-fixture.py` performs the live retrieval once and freezes
it. Five documents, retrieved 2026-10-03T19:18:35Z, bytes stored **verbatim**:

| Slug | Bytes | Patterns | Category | Download gated | Disclaimer |
|------|-------|----------|----------|----------------|------------|
| `linear.app` | 24 354 | 19 | productivity-saas | yes | yes |
| `cursor` | 21 771 | 17 | developer-tools-ides | yes | yes |
| `warp` | 24 438 | 16 | developer-tools-ides | yes | yes |
| `vercel` | 41 405 | 18 | developer-tools-ides | yes | yes |
| `cohere` | 20 020 | 16 | ai-llm-platforms | yes | yes |

Provenance — URL, retrieval timestamp, content digest, normalised digest, source
class, patterns, limitations — is in
`src/ariadne_engine/design_reference/fixtures/getdesign-md/retrieval.json`.

The bytes are unmodified. Reformatting them would break the binding between the
recorded digest and what the site returned, and a regression suite that tested
reformatted input would be testing the reformatter.

## Search behaviour (deterministic)

`getdesign.search` is lexical: significant query words plus any matching industry
intent vocabulary from a declared table, scored by where the term appears (brand 6,
summary 2, `best_for` 1.5, category 1) with a +2 bonus for strong terms. Every
candidate carries the list of terms that matched, so a reviewer can see why it was
returned.

Measured against the recorded 73-row index:

| Query | Top results |
|-------|-------------|
| `developer tooling` | cursor, warp, mongodb, vercel, posthog |
| `dense technical interface` | clickhouse, sentry, kraken, together.ai, hashicorp |
| `cinematic automotive` | tesla, ferrari, lamborghini, bugatti, bmw |
| `premium finance dashboard` | kraken, binance, coinbase, revolut, mastercard |
| `dark productivity app` | linear.app, raycast, notion, resend, apple |
| `editorial brutalism` | cursor, sanity, warp, mongodb, theverge |

Deterministic and stable: identical queries return identical orderings, ties broken
by slug.

## Known brittleness

Recorded honestly, because these are the things most likely to break first:

1. **Markup coupling.** `parse_entry_html` and `parse_catalog_html` depend on an
   `<h1>`, a `<meta name=description>`, a canonical link and semantic anchor shape.
   A redesign of the site would degrade them to fewer fields and a recorded
   `problems` list — not to a crash. The adapter treats degradation as the expected
   failure mode.
2. **Raw path coupling.** `design-md/{slug}/DESIGN.md` in the repository is a
   convention, not a contract. If it changes, retrieval returns 404 and the adapter
   reports a rejected candidate; the offline corpus keeps the regression suite
   working regardless.
3. **Slug drift.** Slugs are host-like and occasionally surprising (`cal` for
   Cal.com). Ariadne never derives a slug from a brand name.
4. **Search recall.** Lexical matching will miss a relevant entry whose description
   shares no vocabulary with the query. This is a known, accepted weakness: an
   unauditable embedding model would be a worse answer than an honest lexical one
   that can be inspected.
5. **Live integration is manual.** By design. No scheduled re-recording exists; the
   fixture is refreshed by running the recorder by hand.

## The separate `getdesign` project — NOT getdesign.md

A different repository, a different goal, a different maintainer:

```text
repository  : MohtashamMurshid/getdesign   (MIT)
homepage    : getdesign.app
goal        : on-demand design-system extraction from ANY url
```

Verified surface state at implementation time (2026-10-03):

| Surface | State | Source |
|---------|-------|--------|
| Web app | implemented (`apps/web`) | README |
| Agent skill | implemented (`skills/getdesign`) | README |
| HTTP API | **planned, not implemented** | README |
| CLI | **placeholder** (`packages/cli`) | README |
| TypeScript SDK | **placeholder** (`packages/sdk`) | README |

**Ariadne codes against none of the planned surfaces.** No HTTP API call, no SDK
import, no CLI invocation exists in this codebase.

What was studied: the documented 9-section extraction contract
(*Visual Theme & Atmosphere · Colour Palette & Roles · Typography Rules · Component
Stylings · Layout Principles · Depth & Elevation · Do's and Don'ts · Responsive
Behaviour · Agent Prompt Guide*), its grounding-in-fetched-CSS principle, its
screenshot requirements, and its anti-hallucination stance.

What was reused:

| Item | Disposition |
|------|-------------|
| 9-section vocabulary | studied; Ariadne's controlled pattern dimensions were written independently against the public corpus, not copied |
| Grounding principle (ground in inspected CSS, not recollection) | adopted as a **principle**, reimplemented independently |
| Token extraction concepts | reimplemented independently; Ariadne's parser targets the Google Stitch frontmatter shape |
| Anti-hallucination rules | adopted as a **principle**; independently implemented as `limitations` + the injection boundary |
| Source code | **none copied, none adapted.** MIT permits reuse; none was needed. |

Ariadne is **not** affiliated with, endorsed by, or "powered by" either project.
Ariadne also does not brand itself "getdesign mode" — the user-facing language is
*Design References · Reference Set · Design Evidence · Design Direction*, with the
provider named only in provenance and advanced diagnostics.

## Integration classification, restated

getdesign.md is a **useful curated source, not ground truth**. It is genuinely good
evidence about how a design system reads from the outside, it is MIT-licensed so
the reuse is clean, and it is honest about its own provenance. It is not a
first-party design system, it is not current by default, and its entry for a famous
brand carries exactly as much authority as its entry for an obscure one: one
third party's reading. Ariadne records that and refuses to launder it.