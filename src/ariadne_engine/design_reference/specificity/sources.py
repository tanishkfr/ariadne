"""The design source ecosystem: role, capability, and honest availability (AR-222D).

AR-220 proved that reference acquisition works. AR-222D generalises it, because the
interesting failure is not "can Ariadne fetch a page" -- it is:

> **A registry entry is not an integration.**

It is trivially easy to produce a list of thirty-six sources and call it an ecosystem.
Doing so is worse than having no list, because the list then reads as thirty-six
integrations. So this module's second job is to make the difference **visible in the
data**: every source declares what Ariadne can actually *do* with it
(:data:`CAPABILITIES`), and a source with no defensible access mechanism is classified
``BROWSER_RESEARCH_SOURCE`` and marked disabled with a reason.

Four permanent rules, each enforced rather than asserted:

* **Do not build thirty-six scrapers.** A source becomes an automated adapter only with a
  public documented API, public MCP, public CLI, public repository, explicit
  machine-readable feed, or permitted deterministic browser access. Everything else stays
  browser-research or disabled.
* **Transport is not trust.** MCP, CLI and browser content is external data. A source
  cannot assert its own authority, and provider metadata that lies about capability is a
  contradiction the registry reports.
* **Implementation sources are not aesthetic authority.** A component existing on a
  registry is not a reason to use it. See :func:`authority_check`.
* **Inspiration does not grant reuse rights.** A visual reference informs hierarchy,
  rhythm and composition. It does not license copying source code, branded assets or an
  exact composition.

Every entry below was verified against the live public surface on the date recorded in
``verified_at``. Where verification found something other than what the marketing page
claims -- a 401 that means "not found" rather than "paywalled", a "MIT licensed" claim
with no license file, a licence that is *not* the one usually assumed -- that is recorded
in ``verification_notes`` rather than smoothed away.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from ...contracts import ContractError

SOURCE_ROLES = (
    "DESIGN_SYSTEM",
    "VISUAL_REFERENCE",
    "PRODUCT_PATTERN",
    "COMPONENT_PATTERN",
    "IMPLEMENTATION_REGISTRY",
    "MOTION_REFERENCE",
    "ASSET_SOURCE",
    "TECHNICAL_CAPABILITY",
)
"""What a source is *for*. A source may hold several roles.

Role is what drives selection. "I need data-table patterns" is a
``COMPONENT_PATTERN`` need, and no amount of ``MOTION_REFERENCE`` evidence answers it.
"""

SOURCE_CAPABILITIES = (
    "SEARCH",
    "INSPECT",
    "DESIGN_MD",
    "SCREENSHOTS",
    "VIDEO",
    "COMPONENT_CODE",
    "MCP",
    "CLI",
    "API",
    "BROWSER_ONLY",
    "DOWNLOAD",
)
"""What Ariadne can actually do with a source.

``API``/``MCP``/``CLI`` describe a *stable documented* mechanism, not an HTTP endpoint
that happens to answer. ``BROWSER_ONLY`` is an honest capability rather than a missing
one: it means a human or a permitted browser session is the retrieval method, and an
adapter will not be built.
"""

ACCESS_MODES = ("public", "login", "paid", "account")
MACHINE_READABLE = ("REGISTRY_JSON", "API_JSON", "NPM_PACKAGE", "GIT_REPOSITORY",
                    "DESIGN_MD", "HTML_ONLY", "VIDEO_ONLY", "BINARY_ASSETS")

ADAPTER_STATUS = (
    "ADAPTER_AVAILABLE",
    "ADAPTER_VENDOR_KEY_REQUIRED",
    "REGISTRY_ONLY",
    "BROWSER_RESEARCH_SOURCE",
    "DISABLED",
)
"""The only states a source may be in.

``REGISTRY_ONLY`` is the interesting one: the source *is* machine-readable, but its
licence forbids the redistribution an adapter would perform, or the catalogue is frozen.
Recording it as an available integration would be the lie this taxonomy exists to stop.

``ADAPTER_VENDOR_KEY_REQUIRED`` is separate from ``ADAPTER_AVAILABLE`` because "there is a
documented API" and "you may use it right now" are different facts, and conflating them is
how an unauthenticated free tier becomes an assumed capability.
"""

LICENCE_UNVERIFIED_MARKERS = (
    "asserted", "unverified", "not verified", "no licence grant", "all rights reserved",
    "no rights reserved",
)
"""Phrases that mean the licence is not established.

An unestablished licence is not a permissive one. This is the Book of Shaders case: widely
assumed to be CC BY-NC-SA, and actually all-rights-reserved."""

VERIFIED_ON = "2026-10-05"
"""Every entry's live-surface check. A registry with no verification date is a memory."""


def _source(
    source_id: str,
    display_name: str,
    roles: Sequence[str],
    capabilities: Sequence[str],
    *,
    access_mode: str = "public",
    authentication: str = "none",
    paid_access: bool = False,
    machine_readable: str = "HTML_ONLY",
    license_visibility: str = "",
    reuse_policy: str = "",
    prohibited_uses: Sequence[str] = (),
    adapter_status: str = "BROWSER_RESEARCH_SOURCE",
    adapter_id: str = "",
    endpoint: str = "",
    terms_notes: str = "",
    verification_notes: str = "",
    enabled: bool = True,
    disabled_reason: str = "",
    selection_notes: str = "",
) -> dict:
    return {
        "source_id": source_id,
        "display_name": display_name,
        "source_roles": list(roles),
        "capabilities": list(capabilities),
        "access_mode": access_mode,
        "authentication": authentication,
        "paid_access": bool(paid_access),
        "machine_readable": machine_readable,
        "license_visibility": license_visibility,
        "reuse_policy": reuse_policy,
        "prohibited_uses": list(prohibited_uses),
        "adapter_status": adapter_status,
        "adapter_id": adapter_id,
        "endpoint": endpoint,
        "terms_notes": terms_notes,
        "verification_notes": verification_notes,
        "enabled": bool(enabled),
        "disabled_reason": str(disabled_reason),
        "selection_notes": selection_notes,
        "verified_at": VERIFIED_ON,
    }


# --------------------------------------------------------------- the catalogue
#
# Verified against the live surface on VERIFIED_ON. Entries marked DISABLED are kept
# rather than deleted: a source that stopped existing, stopped being machine-readable, or
# turned out to be something other than its name suggests is a finding worth retaining,
# and deleting it means the next person re-investigates it.

SOURCE_CATALOG: tuple[dict, ...] = (
    # -- implementation registries: shadcn ecosystem ---------------------------
    _source(
        "shadcn", "shadcn/ui", ("IMPLEMENTATION_REGISTRY", "COMPONENT_PATTERN", "DESIGN_SYSTEM"),
        ("CLI", "MCP", "API", "COMPONENT_CODE", "SEARCH", "INSPECT"),
        machine_readable="REGISTRY_JSON",
        license_visibility="MIT (LICENSE.md verified in the public repository)",
        reuse_policy="MIT: reuse, modification and redistribution permitted with the notice retained",
        adapter_status="ADAPTER_AVAILABLE",
        adapter_id="shadcn-registry",
        endpoint="https://ui.shadcn.com/r/registries.json",
        terms_notes="no published automation clause against the CLI, registry spec or MCP",
        verification_notes=(
            "418 public registries with live health and ranking scores; schemas published at "
            "/schema/registry.json and /schema/registry-item.json; stdio MCP via "
            "'npx shadcn@latest mcp'. Core components no longer resolve at guessable flat paths "
            "(--/r/button.json is 404) and must be resolved through the @shadcn namespace. The "
            "directory carries live health monitoring, so a snapshot of scores is not stable"
        ),
        selection_notes=(
            "the substrate the other shadcn-spec registries resolve through. Use for implementation "
            "primitives and component patterns; its design tokens are evidence, not authority"
        ),
    ),
    _source(
        "magicui", "Magic UI", ("IMPLEMENTATION_REGISTRY", "MOTION_REFERENCE", "COMPONENT_PATTERN"),
        ("CLI", "API", "COMPONENT_CODE", "SEARCH", "INSPECT"),
        machine_readable="REGISTRY_JSON",
        license_visibility="MIT asserted by the public repository; the site itself has no licence page",
        reuse_policy="MIT by repository licence; verify before shipping",
        adapter_status="ADAPTER_AVAILABLE",
        adapter_id="shadcn-registry",
        endpoint="https://magicui.design/r/registry.json",
        terms_notes="robots.txt allows / and disallows /api/; the /r/ registry endpoints are unaffected",
        verification_notes=(
            "250 items served as shadcn-spec JSON with inline content, no login. No npm package -- "
            "delivery is 'npx shadcn@latest add @magicui/*'. Licence exists only in the repository, "
            "not on the site"
        ),
        selection_notes="motion and animated text primitives; select against a recorded motion intent",
    ),
    _source(
        "motion-primitives", "Motion Primitives", ("MOTION_REFERENCE", "IMPLEMENTATION_REGISTRY"),
        ("CLI", "API", "COMPONENT_CODE", "SEARCH", "INSPECT"),
        machine_readable="REGISTRY_JSON",
        license_visibility="MIT asserted by the public repository; no site licence page",
        reuse_policy="MIT by repository licence; verify before shipping",
        adapter_status="ADAPTER_AVAILABLE",
        adapter_id="shadcn-registry",
        endpoint="https://motion-primitives.com/c/registry.json",
        terms_notes="no published automation clause",
        verification_notes=(
            "33 items, no login. The '.json' suffix is MANDATORY: the bare /c/registry path returns "
            "404. No npm package; delivery is 'npx shadcn@latest add @motion-primitives/*'"
        ),
        selection_notes=(
            "the strongest source for motion intent evidence. A REWARD or SPATIAL_CONTINUITY need "
            "is what justifies querying it -- not 'the page could use animation'"
        ),
    ),
    _source(
        "smoothui", "SmoothUI", ("IMPLEMENTATION_REGISTRY", "COMPONENT_PATTERN"),
        ("CLI", "API", "COMPONENT_CODE", "SEARCH", "INSPECT"),
        machine_readable="REGISTRY_JSON",
        license_visibility="MIT (LICENSE verified in the public repository)",
        reuse_policy="MIT: reuse permitted with the notice retained",
        adapter_status="ADAPTER_AVAILABLE",
        adapter_id="shadcn-registry",
        endpoint="https://smoothui.dev/r/registry.json",
        terms_notes="robots.txt allows / and disallows /api/ /og/ /blocks/preview/",
        verification_notes=(
            "246 items with inline content in a single 2.4 MB request -- the cheapest adapter of the "
            "set. Per-item endpoints /r/{name}.json return HTTP 500, so the index is the only path. "
            "The domain is smoothui.dev, NOT smoothui.com, which is an unrelated site. The release "
            "config references an npm package 'smoothui' that is not published"
        ),
        selection_notes="component patterns where a single bounded request is preferable to N requests",
    ),
    _source(
        "microkit", "Microkit", ("IMPLEMENTATION_REGISTRY", "COMPONENT_PATTERN"),
        ("CLI", "API", "COMPONENT_CODE", "SEARCH", "INSPECT"),
        machine_readable="REGISTRY_JSON",
        license_visibility=(
            "ASSERTED MIT by the shadcn directory listing; no licence page and no located public "
            "repository. Treated as unverified"
        ),
        reuse_policy="unverified -- confirm before shipping anything derived from it",
        adapter_status="REGISTRY_ONLY",
        adapter_id="",
        endpoint="https://microkit.co/r/registry.json",
        terms_notes="no published automation clause",
        verification_notes=(
            "49 items, no login, '.json' suffix mandatory. The domain is microkit.co -- microkit.one "
            "does not resolve. Licence is asserted rather than published, which is exactly the "
            "condition that must not be treated as reusable"
        ),
        selection_notes="record-only until the licence is confirmed from a primary source",
    ),
    _source(
        "aceternity", "Aceternity UI", ("IMPLEMENTATION_REGISTRY", "VISUAL_REFERENCE"),
        ("API", "COMPONENT_CODE", "SEARCH", "INSPECT"),
        machine_readable="REGISTRY_JSON",
        license_visibility=(
            "Proprietary 'Aceternity License'. Not open source. Per-component variance is explicitly "
            "permitted: some items embed third-party components under their own licences"
        ),
        reuse_policy=(
            "free tier: unlimited personal and commercial end products, modifiable. PROHIBITED: "
            "redistribution of the item or its source files, resale on any marketplace, and sale of "
            "derivative themes or templates. Third-party components inside an item keep their own licence"
        ),
        prohibited_uses=(
            "redistributing the Item as a stock asset or its source files",
            "selling, reselling or distributing the Item or derivatives on any marketplace",
            "creating themes, templates or derivative products to sell on any marketplace",
            "ignoring third-party component licences embedded inside an Item",
        ),
        adapter_status="REGISTRY_ONLY",
        adapter_id="",
        endpoint="https://ui.aceternity.com/registry/registry.json",
        terms_notes="paid tiers from $169/year; registry health reported degraded (item_validation_failures)",
        verification_notes=(
            "~293 items served with inline content and no login wall on the free tier. An unknown "
            "item name returns 401, which LOOKS like a paywall but is a soft-404 -- so existence "
            "checks cannot distinguish 'unknown item' from 'gated item'. Real domain is "
            "ui.aceternity.com; aceternity.com redirects"
        ),
        selection_notes=(
            "technically automatable but deliberately not adapted: the licence prohibits the "
            "redistribution an adapter performs. Metadata may be recorded; code may be used only "
            "inside a shipped end product, audited per item for third-party licence variance"
        ),
    ),
    _source(
        "shadcnblocks", "shadcnblocks", ("IMPLEMENTATION_REGISTRY", "COMPONENT_PATTERN"),
        ("API", "SEARCH", "INSPECT"),
        machine_readable="REGISTRY_JSON",
        license_visibility="Proprietary paid licence; the free subset is governed by Terms only",
        reuse_policy=(
            "purchased licence grants non-exclusive rights in end products. The licence expressly "
            "treats AI-assisted transformation as a Derivative. Free blocks carry no open-source grant"
        ),
        prohibited_uses=(
            "republishing blocks without a purchased licence",
            "reselling or redistributing blocks or derivative themes",
            "extracting block source for redistribution as a stock asset",
        ),
        adapter_status="REGISTRY_ONLY",
        adapter_id="",
        endpoint="https://www.shadcnblocks.com/r/registry.json",
        terms_notes="www host required; non-www redirects. Registry health degraded",
        verification_notes=(
            "4,351 items, public spec-correct registry with no inline content. The free/paid split is "
            "not machine-readable, and the Terms that govern the free tier were not retrieved -- "
            "treated as unverified for automated retrieval"
        ),
        selection_notes="record-only; do not redistribute. Treat as a lead, not as an integration",
    ),
    _source(
        "21st-dev", "21st.dev", ("IMPLEMENTATION_REGISTRY", "COMPONENT_PATTERN"),
        ("API", "MCP", "CLI", "SEARCH", "COMPONENT_CODE"),
        access_mode="account", authentication="api key (x-api-key or bearer)",
        machine_readable="API_JSON",
        license_visibility=(
            "per-component and NOT resolvable from the API. Component code may be third-party authored "
            "and separately licensed"
        ),
        reuse_policy=(
            "obtaining code grants no right to demos, previews or media. Resolve each component's own "
            "licence from the item itself; assume unknown until stated"
        ),
        prohibited_uses=(
            "scraping or automatically collecting data from the Marketplace through web scraping, "
            "bots, crawlers or any other automated means",
            "using Marketplace content, code or data to train AI or ML models",
            "redistributing, selling or licensing Marketplace content without authorization",
            "republishing structured metadata (titles, descriptions, tags) by manual or automated means",
        ),
        adapter_status="ADAPTER_AVAILABLE",
        adapter_id="21st-api",
        endpoint="https://21st.dev/api/v1",
        terms_notes=(
            "TERMS SECTION 3 PROHIBITS, without explicit written consent: scraping or automated "
            "collection, use of content to train models, redistribution, and republishing structured "
            "metadata by any means. robots.txt permits named AI crawlers yet disallows /api/ -- the "
            "sanctioned path is the documented API/MCP/CLI only"
        ),
        verification_notes=(
            "public OpenAPI 3.0 spec at /openapi.json, RFC 9727 catalog, public llms.txt, HTTP MCP at "
            "/api/mcp, and npm @21st-dev/cli (MIT). All data endpoints are key-gated. The free tier is "
            "metered at 2 component code retrievals per day; search is unmetered"
        ),
        selection_notes=(
            "adapted through the sanctioned API only. Never scrape, and never harvest metadata -- the "
            "Terms forbid republishing it by any means. The 2/day free cap makes it unsuitable for "
            "bulk ingestion; search-then-fetch is the intended shape"
        ),
    ),
    # -- technical capability --------------------------------------------------
    _source(
        "animejs", "Anime.js", ("TECHNICAL_CAPABILITY", "MOTION_REFERENCE"),
        ("API", "DOWNLOAD", "INSPECT"),
        machine_readable="NPM_PACKAGE",
        license_visibility="MIT (SPDX identifier and raw LICENSE verified)",
        reuse_policy="MIT",
        adapter_status="ADAPTER_AVAILABLE",
        adapter_id="npm-package",
        endpoint="https://www.npmjs.com/package/animejs",
        terms_notes="MIT governs the code; no scraping surface",
        verification_notes="npm 'animejs' 4.5.0, GitHub juliangarnier/anime, bundled TypeScript types",
        selection_notes=(
            "a motion *capability*, consulted only when a recorded motion intent needs a timeline "
            "beyond CSS. Its existence is not a reason to animate"
        ),
    ),
    _source(
        "threejs", "Three.js", ("TECHNICAL_CAPABILITY", "ASSET_SOURCE"),
        ("API", "DOWNLOAD", "INSPECT"),
        machine_readable="NPM_PACKAGE",
        license_visibility="MIT (SPDX identifier and raw LICENSE verified)",
        reuse_policy="MIT",
        adapter_status="ADAPTER_AVAILABLE",
        adapter_id="npm-package",
        endpoint="https://www.npmjs.com/package/three",
        terms_notes="MIT governs the code",
        verification_notes=(
            "npm 'three' 0.186.1, GitHub mrdoob/three.js. Types are a separate package (@types/three). "
            "The default branch is 'dev', not 'main', and a full clone is ~2 GB"
        ),
        selection_notes=(
            "only for a direction whose richness source is SPATIAL_3D. A 3D scene added to a "
            "direction that did not ask for it is decoration, not richness"
        ),
    ),
    _source(
        "shadertoy", "Shadertoy", ("TECHNICAL_CAPABILITY", "ASSET_SOURCE", "VISUAL_REFERENCE"),
        ("API", "SEARCH", "INSPECT"),
        access_mode="account", authentication="free API key issued per account",
        machine_readable="API_JSON",
        license_visibility=(
            "PER-SHADER. Authors set their own licence per shader and there is no catalogue-wide "
            "licence. Attribution to the Shadertoy API is MANDATORY for any product using it"
        ),
        reuse_policy=(
            "respect each shader's own licence. Only shaders marked Public AND API are reachable. "
            "Any product using the API must display that it uses the Shadertoy API"
        ),
        adapter_status="ADAPTER_VENDOR_KEY_REQUIRED",
        adapter_id="shadertoy-api",
        endpoint="https://www.shadertoy.com/api/v1",
        terms_notes="ToS reserves the right to block any shader or asset without notice; robots.txt 403s non-browsers",
        verification_notes=(
            "documented REST API v1 with a free key: /api/v1/shaders/query/{string}, "
            "/api/v1/shaders/{shaderID}. No official SDK. Public-but-not-API, Unlisted and Anonymous "
            "shaders are invisible to the API, so the corpus is a subset of the site"
        ),
        selection_notes=(
            "a shader research corpus, not a component registry. Licence resolution is per result, so "
            "a run that queries it must carry an attribution string and per-item licence evidence"
        ),
    ),
    _source(
        "liquid-glass", "Liquid Glass", ("IMPLEMENTATION_REGISTRY", "TECHNICAL_CAPABILITY"),
        ("API", "DOWNLOAD", "INSPECT"),
        machine_readable="NPM_PACKAGE",
        license_visibility="MIT (SPDX identifier verified in the public repository)",
        reuse_policy="MIT",
        adapter_status="ADAPTER_AVAILABLE",
        adapter_id="npm-package",
        endpoint="https://www.npmjs.com/package/@samasante/liquid-glass",
        terms_notes="MIT; nothing to scrape",
        verification_notes=(
            "npm '@samasante/liquid-glass' 0.1.1, GitHub samasante/liquid-glass. A headless React lens "
            "that refracts live DOM via an SVG filter. NOTE: 'glass.samasante' does not resolve; the "
            "working demo host is glass.samasante.com. Version 0.1.1 -- expect API churn"
        ),
        selection_notes=(
            "the correct way to obtain a refract-glass *capability* without inventing one. Still "
            "subject to the random-glass default pattern: content must genuinely pass behind"
        ),
    ),
    # -- reference galleries: no automatable mechanism -------------------------
    _source(
        "uiverse", "Uiverse", ("VISUAL_REFERENCE", "COMPONENT_PATTERN"),
        ("BROWSER_ONLY", "INSPECT"),
        machine_readable="HTML_ONLY",
        license_visibility="MIT sitewide on the stale official mirror",
        reuse_policy=(
            "the frozen mirror is MIT and reusable as a 2024 snapshot. The live catalogue is "
            "bot-walled and has no open licence grant surfaced for automated retrieval"
        ),
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://uiverse.io",
        terms_notes=(
            "robots.txt is permissive but the site returns 403 to non-browser clients and "
            "/developers is 403, so permissiveness is theoretical. No official API; legacy /api/* 403"
        ),
        verification_notes=(
            "the official GitHub mirror uiverse-io/galaxy is MIT but was last pushed 2024-09-02 -- "
            "stale by over two years, and missing the 'loaders' category. Any third-party MCP for "
            "Uiverse clones this stale repo and is not an authoritative surface"
        ),
        selection_notes="human browser research only. No adapter will be built",
    ),
    _source(
        "3d-icons", "3D Icons", ("ASSET_SOURCE", "VISUAL_REFERENCE"),
        ("BROWSER_ONLY", "DOWNLOAD"),
        machine_readable="BINARY_ASSETS",
        license_visibility="CC0-1.0 'No Rights Reserved' (SPDX verified)",
        reuse_policy="CC0: personal and commercial use, NO attribution required. The most permissive licence in this registry",
        adapter_status="REGISTRY_ONLY",
        adapter_id="",
        endpoint="https://3dicons.co",
        terms_notes="robots.txt disallows /icons/download/ and /privacy-policy",
        verification_notes=(
            "the domain is 3dicons.co -- 3dicons.org does not resolve. Binary renders (PNG, Figma, "
            "Blender, FBX), not code. The public repo is realvjy/3dicons (CC0) on branch 'develop', "
            "last pushed 2024-12-22 -- stale"
        ),
        selection_notes=(
            "CC0 means the repo contents are freely reusable, but there is no code and the bulk "
            "asset path is robots-disallowed, so record-only"
        ),
    ),
    _source(
        "book-of-shaders", "The Book of Shaders",
        ("TECHNICAL_CAPABILITY", "VISUAL_REFERENCE"),
        ("BROWSER_ONLY",),
        machine_readable="HTML_ONLY",
        license_visibility=(
            "ALL RIGHTS RESERVED. The repository's licence field reads 'Other' and the LICENSE text "
            "says 'Copyright (c) Patricio Gonzalez Vivo, 2015 ... All rights reserved.'"
        ),
        reuse_policy=(
            "NO reuse or redistribution of text, translations or lesson code. This is NOT the "
            "CC BY-NC-SA licence the project is widely assumed to carry, and that assumption is "
            "exactly the failure mode this field exists to catch"
        ),
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://thebookofshaders.com",
        terms_notes="no robots.txt at all, so no automation guidance either way",
        verification_notes="static site plus a GitHub repo whose declared licence is not open source",
        selection_notes=(
            "learn GLSL from it. Do not ingest or redistribute. For licensed shader material use the "
            "Shadertoy API or Three.js's own MIT-licensed examples"
        ),
    ),
    _source(
        "threejs-journey", "Three.js Journey", ("VISUAL_REFERENCE",),
        ("BROWSER_ONLY", "VIDEO"),
        access_mode="paid", authentication="account", paid_access=True,
        machine_readable="VIDEO_ONLY",
        license_visibility="NO LICENCE GRANTED",
        reuse_policy=(
            "the terms state that no property is transmitted and no right or licence is granted "
            "beyond use of the platform during the contract term. Strictly personal use, no "
            "redistribution, no derivative component reuse"
        ),
        prohibited_uses=(
            "redistributing the course materials or any derivative of them",
            "reselling or licensing course content",
            "using the material without an account or a purchased licence",
            "publishing course code as a derivative work",
        ),
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://threejs-journey.com",
        terms_notes="paid from $95/course; general-conditions govern",
        verification_notes=(
            "the domain is threejs-journey.com (hyphenated); the unhyphenated form returns 503 to "
            "non-browsers. No API, no CLI, no MCP, no public repository for course materials"
        ),
        selection_notes="paid and licence-restricted: no adapter is permissible. Use Three.js's own MIT docs instead",
    ),
    # -- verified as absent ---------------------------------------------------
    _source(
        "kinetics", "Kinetics", ("COMPONENT_PATTERN",),
        (),
        adapter_status="DISABLED",
        enabled=False,
        disabled_reason=(
            "does not exist. The host kinetics.nexxt.ai returns NXDOMAIN; nexxt.ai resolves but is an "
            "unrelated AI consultancy, and kinetics.dev is an unrelated product. Retained as a "
            "finding so it is not re-investigated"
        ),
        verification_notes="NXDOMAIN on 2026-10-05",
    ),
    _source(
        "kitbitz", "KitBitz", ("COMPONENT_PATTERN", "VISUAL_REFERENCE"),
        (),
        adapter_status="DISABLED",
        enabled=False,
        disabled_reason=(
            "the domain is parked. It returns 200 with a LANDER_SYSTEM parking page and a sitemap "
            "containing exactly one URL. No components, no code, no licence, no API"
        ),
        verification_notes="domain parking confirmed on 2026-10-05",
    ),
    # -- DESIGN.md providers: distinct identities, never collapsed ------------
    _source(
        "getdesign", "getdesign.md", ("DESIGN_SYSTEM", "VISUAL_REFERENCE"),
        ("DESIGN_MD", "SEARCH", "INSPECT", "CLI"),
        machine_readable="DESIGN_MD",
        license_visibility=(
            "Terms section 5: public-directory DESIGN.md files are free to browse, download and use "
            "in your projects, as is, and are explicitly NOT official design systems"
        ),
        reuse_policy=(
            "artefacts are usable; the directory's own terms prohibit scraping the SERVICE, "
            "impersonating referenced brands, copying third-party logos and reselling paid deliverables"
        ),
        prohibited_uses=(
            "automated scraping of the site",
            "attempting to circumvent payment, access controls or rate limits",
            "impersonating a referenced brand",
            "reselling paid deliverables",
        ),
        adapter_status="ADAPTER_AVAILABLE",
        adapter_id="ariadne.getdesign",
        endpoint="https://getdesign.md",
        terms_notes=(
            "section 7 Acceptable Use prohibits automated scraping of the service. The clean channels "
            "are the GitHub repository and the npm CLI, which are separately licensed and carry none "
            "of that restriction"
        ),
        verification_notes=(
            "the AR-220 corpus path, preserved unchanged: 74 MIT DESIGN.md files shipped as a frozen "
            "fixture so every regression test stays offline. The public site serves 550+ entries; its "
            "/llms.txt returns HTTP 200 but is the SPA HTML shell titled '0 DESIGN.md files' and is "
            "NOINDEX -- an adapter must not be wired to it"
        ),
        selection_notes=(
            "the existing AR-220 path, unchanged. Kept as its own source identity: the directory, the "
            "GitHub repository and designmd.ai are three providers of DESIGN.md-shaped material and "
            "collapsing them into one entry would hide the licence differences between them"
        ),
    ),
    _source(
        "awesome-design-md", "awesome-design-md (GitHub)",
        ("DESIGN_SYSTEM", "TECHNICAL_CAPABILITY"),
        ("DESIGN_MD", "DOWNLOAD", "INSPECT", "CLI"),
        machine_readable="GIT_REPOSITORY",
        license_visibility="MIT (public repository, verified)",
        reuse_policy=(
            "MIT. The repository states that extracted design tokens are publicly visible CSS values "
            "and that no claim is made over any site's visual identity"
        ),
        adapter_status="ADAPTER_AVAILABLE",
        adapter_id="git-repository",
        endpoint="https://github.com/VoltAgent/awesome-design-md",
        terms_notes="MIT governs the repository; none of the directory's ToS restrictions apply to it",
        verification_notes=(
            "230 entries, 74 DESIGN.md files each with light and dark previews. The npm CLI 'getdesign' "
            "(MIT) bundles all 74 files locally, so it works fully offline -- the only network call "
            "is a download-counting telemetry POST"
        ),
        selection_notes=(
            "the licence-clean way to obtain DESIGN.md material, and the one to prefer over the "
            "directory site. Offline-capable, so it needs no network and no ToS judgement"
        ),
    ),
    _source(
        "designmd-ai", "designmd.ai", ("DESIGN_SYSTEM", "VISUAL_REFERENCE"),
        ("DESIGN_MD", "SEARCH", "INSPECT", "CLI", "MCP"),
        access_mode="account", authentication="free personal API key (never shared)",
        machine_readable="DESIGN_MD",
        license_visibility="PER-KIT. Each record carries its own uploader-chosen licence (MIT observed)",
        reuse_policy=(
            "uploader retains ownership and grants designmd.ai a licence. A run must read the "
            "per-record licence; a corpus-wide assumption is not available"
        ),
        adapter_status="ADAPTER_VENDOR_KEY_REQUIRED",
        adapter_id="designmd-cli",
        endpoint="https://designmd.ai",
        terms_notes=(
            "robots.txt says Disallow: /api/ while the site's own CLI and MCP call /api/v1/. "
            "Resolution: use the official clients only. Do not build a bespoke HTTP client against "
            "/api/v1/, because it contradicts the site's own robots policy"
        ),
        verification_notes=(
            "421 kits. Public MIT CLI 'designmd' and MCP 'designmd-mcp' on npm, both with --json. "
            "The filter parameter is 'tags' (plural); 'tag=' is silently ignored and returns "
            "unfiltered results, which is the kind of quiet wrong answer an adapter must not inherit. "
            "The documented key requirement on /download does not match observed behaviour -- treat "
            "that as a documentation bug, not as permission"
        ),
        selection_notes=(
            "a distinct DESIGN.md provider from getdesign, with its own licence model and its own "
            "robots conflict. Collapsing the two would hide both"
        ),
    ),
    _source(
        "refero", "Refero / styles.refero.design", ("VISUAL_REFERENCE", "PRODUCT_PATTERN", "DESIGN_SYSTEM"),
        ("SEARCH", "INSPECT", "BROWSER_ONLY"),
        access_mode="paid", authentication="account; MCP requires Pro/Team", paid_access=True,
        machine_readable="HTML_ONLY",
        license_visibility="Terms of Use section 10 and 13: Refero Content is for design research and comparison",
        reuse_policy=(
            "normal design work, and insights applied to your own products, are permitted. Resale, "
            "redistribution, sublicensing and commercial syndication are prohibited"
        ),
        prohibited_uses=(
            "training, fine-tuning, evaluating or improving machine learning models or datasets",
            "creating datasets, benchmarks or a competing product or search index",
            "reselling, redistributing or sublicensing Refero Content",
            "using the MCP or REST surfaces without a purchased licence or an issued token",
            "scraping, crawling, automation or systematic extraction outside documented download features",
        ),
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://styles.refero.design",
        terms_notes=(
            "THE MOST RESTRICTIVE TERMS IN THE REGISTRY. Section 13 prohibits model training, "
            "fine-tuning, benchmarking and dataset creation, and this holds for paying MCP users. "
            "robots.txt allows general agents but explicitly Disallows GPTBot"
        ),
        verification_notes=(
            "a public MCP exists at api.refero.design/mcp (Pro/Team, 8,000 calls/month/licensed user) "
            "and 1,342 style sitemap locs. The documented /sitemap.xml returns HTML with zero locs "
            "while robots.txt points at it; the real file is /site-map.xml. styles.refero.design "
            "browsing is public"
        ),
        selection_notes=(
            "usable as human/agent design research ONLY. Anything that feeds its output into training, "
            "evaluation corpora, dataset construction or a design index is inside the explicitly "
            "prohibited category, and the prohibition survives payment. Fail closed on any use "
            "outside 'apply insights to this project'"
        ),
    ),
    _source(
        "mobbin", "Mobbin", ("PRODUCT_PATTERN", "VISUAL_REFERENCE"),
        ("SEARCH", "INSPECT", "MCP"),
        access_mode="paid", authentication="account; MCP on Pro, REST API on Team",
        paid_access=True, machine_readable="HTML_ONLY",
        license_visibility="Screenshots belong to the source products, not to Mobbin",
        reuse_policy=(
            "observation permitted; verbatim copying of protected designs, branding, text or assets "
            "prohibited. Preserve source links and separate observation from inference"
        ),
        prohibited_uses=(
            "verbatim copying of protected designs, branding, text or assets",
            "using the MCP or REST surfaces without a Pro or Team licence",
            "crawling the application HTML rather than the documented agent files",
        ),
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://mobbin.com",
        terms_notes=(
            "robots.txt allows only the .md/.txt agent files for GPTBot and disallows everything else, "
            "so the documented docs are the sanctioned surface and the HTML app is not. Rate limit 60 "
            "requests per 60 seconds; honour Retry-After"
        ),
        verification_notes=(
            "the strongest programmatic surface in the reference-gallery group: llms.txt, "
            "llms-full.txt, docs.mobbin.com with an openapi.json spec, a live MCP endpoint at "
            "api.mobbin.com/mcp (401 unauthenticated, i.e. live and enforcing), and REST at "
            "api.mobbin.com/v1. Pro is quarterly or yearly only -- there is no monthly interval. "
            "REST requires Team at a higher tier"
        ),
        selection_notes=(
            "the correct PRODUCT_PATTERN source, and the one to reach for when the need is 'how do "
            "real products handle this flow'. Paid, so selection must record the plan assumption"
        ),
    ),
    _source(
        "kage", "Kage", ("VISUAL_REFERENCE", "PRODUCT_PATTERN", "COMPONENT_PATTERN"),
        ("SEARCH", "INSPECT", "BROWSER_ONLY"),
        machine_readable="HTML_ONLY",
        license_visibility=(
            "Terms (10 Sep 2026): generated prompts and analyses are free to use, adapt and build "
            "from, commercially or otherwise, with NO attribution required. Kage claims no copyright "
            "over them. Screenshots remain the property of their own owners"
        ),
        reuse_policy=(
            "the most permissive licence on non-code material in this registry. Screenshots are for "
            "commentary, criticism, education and design inspiration only"
        ),
        prohibited_uses=(
            "scraping, mirroring or bulk downloading the library",
            "overloading the service",
            "accessing the admin area",
            "reproducing a product's branding, copy or artwork",
        ),
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://kage.design",
        terms_notes=(
            "free, no account, no paid tier. Facet-scoped and single-item retrieval are permitted; "
            "bulk mirroring is not. robots.txt disallows /search even though llms.txt links it -- "
            "use facet URLs"
        ),
        verification_notes=(
            "~2,789 sitemap locs and an excellent llms.txt facet index. A free Streamable HTTP MCP at "
            "/mcp is documented as 'free and open, no API key', but every initialize handshake "
            "returned 400 during verification, so the MCP claim is DOCUMENTED BUT UNCONFIRMED. The "
            "llms.txt and sitemap path is confirmed working. Single-person operated; the operator "
            "states the site may change or disappear without notice"
        ),
        selection_notes=(
            "free and licence-permissive for prompt-level material. Treated as browser research "
            "because the MCP could not be confirmed, and an unconfirmed transport is not a transport"
        ),
    ),
    _source(
        "land-book", "Land-book", ("VISUAL_REFERENCE",),
        ("SEARCH", "INSPECT"),
        machine_readable="RSS",
        license_visibility="Not a content licence. llms.txt gives attribution guidance, not a grant",
        reuse_policy=(
            "link to the source page and credit the named designer. Template listings are affiliate "
            "links. No reuse of the screenshots themselves is granted"
        ),
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://land-book.com/rss.xml",
        terms_notes=(
            "EXPLICITLY PERMISSIVE: robots.txt names AI crawlers individually and states they share "
            "the same rules as every other bot. Disallowed: /api/, auth paths, and all filter/sort/"
            "tracking query parameters -- so it must not be driven via filtered query strings"
        ),
        verification_notes=(
            "~10,497 items. Working RSS 2.0 plus llms.txt with attribution guidance, and JSON-LD "
            "ItemList per page. Two real inconsistencies: /sitemap.xml is advertised in robots but "
            "returns 403, and CDN image URLs carry expiring signature parameters that must not be "
            "persisted"
        ),
        selection_notes="deterministic RSS retrieval is legitimate and permitted; the query-parameter bans are not",
    ),
    _source(
        "awwwards", "Awwwards", ("VISUAL_REFERENCE",),
        ("SEARCH", "INSPECT", "API"),
        machine_readable="API_JSON",
        license_visibility="All rights reserved; content may not be used commercially without authorisation",
        reuse_policy="no reproduction of the site's material; observation and principle capture only",
        prohibited_uses=("reproduction or commercial use of Awwwards material",),
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://www.awwwards.com",
        terms_notes=(
            "a public read-only OpenAPI 3.1 spec exists, but its scope is ANNUAL AWARDS ONLY -- "
            "there is no public endpoint for the website gallery. robots.txt disallows many named "
            "crawlers including psbot, dotbot and SiteSucker"
        ),
        verification_notes=(
            "the apex domain returns 403 to non-browser agents; www is required. The awards nominees "
            "collection is currently empty (totalItems: 0). 24 disallowed path prefixes include "
            "/vote/, /gallery/, /search-websites and /elements/*"
        ),
        selection_notes=(
            "the awards API is deterministic but narrow, and the gallery is not automatable. Treat as "
            "browser research for anything beyond awards metadata"
        ),
    ),
    _source(
        "minimal-gallery", "Minimal Gallery", ("VISUAL_REFERENCE",),
        ("SEARCH", "INSPECT", "BROWSER_ONLY"),
        machine_readable="HTML_ONLY",
        license_visibility="Screenshots, thumbnails and metadata are the site's property",
        reuse_policy=(
            "personal viewing and bookmarking only. Reproduction, distribution, modification or "
            "display of any image for commercial or public purposes requires written permission"
        ),
        prohibited_uses=(
            "scraping",
            "bulk downloading images",
            "republishing any image, thumbnail or metadata",
            "any commercial or public use of the imagery",
        ),
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://minimal.gallery",
        terms_notes=(
            "robots.txt is permissive but the /legal page explicitly names bulk image download and "
            "scraping as prohibited. THE TERMS CONTROL WHERE THE TWO DISAGREE, and this is the "
            "clearest example of that rule in the registry"
        ),
        verification_notes=(
            "public gallery with tag and platform taxonomies; WordPress sitemap available. No paid "
            "tier found; /subscribe/ is a newsletter. Pagination has a trailing-space quirk"
        ),
        selection_notes="observation only, by a human. Never an adapter, never bulk retrieval",
    ),
    _source(
        "recent-design", "recent.design (ex-Godly)", ("VISUAL_REFERENCE", "ASSET_SOURCE"),
        ("SEARCH", "INSPECT", "BROWSER_ONLY"),
        machine_readable="HTML_ONLY",
        license_visibility="NOT STATED. No reuse terms published anywhere on the site",
        reuse_policy="unestablished; observation only",
        prohibited_uses=("bulk retrieval",),
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://recent.design",
        terms_notes="no published terms page found; robots.txt fully permissive",
        verification_notes=(
            "Godly 301-redirects here and the site states it has taken God's place. ~1,114 sitemap "
            "locs. Item ids are short opaque slugs and are unstable. Sponsored cards are injected "
            "into the feed, so ranking is not a quality signal. The rebrand is in progress"
        ),
        selection_notes=(
            "treat as godly only if a legacy reference names it. Very high brittleness: a rebrand in "
            "progress with unstable ids is not something to build an adapter against"
        ),
    ),
    _source(
        "navbar-gallery", "Navbar Gallery", ("VISUAL_REFERENCE",),
        ("SEARCH", "INSPECT", "BROWSER_ONLY"),
        machine_readable="HTML_ONLY",
        license_visibility="NOT STATED. llms.txt describes provenance but grants no licence",
        reuse_policy="observation only; each navbar belongs to a real live website",
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://www.navbar.gallery",
        terms_notes="robots.txt contains no Disallow rules; no terms page found",
        verification_notes=(
            "CORRECTED HOST: navbars.gallery does not resolve; the site is navbar.gallery. 450+ "
            "navbars, 642 sitemap locs, no API. Items come from real live websites"
        ),
        selection_notes="a clean example of one narrow surface worth researching by hand",
    ),
    _source(
        "footer-design", "Footer.design", ("VISUAL_REFERENCE",),
        ("SEARCH", "INSPECT", "BROWSER_ONLY"),
        machine_readable="HTML_ONLY",
        license_visibility="NOT STATED",
        reuse_policy="observation only",
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://www.footer.design",
        terms_notes="robots.txt Allow: /; no terms page (/terms is 404)",
        verification_notes="~817 sitemap locs served with a mismatched rss content-type; 65 curated pages",
        selection_notes="browser research; sitemap enumeration viable if ever needed",
    ),
    _source(
        "cta-gallery", "CTA Gallery", ("VISUAL_REFERENCE",),
        ("SEARCH", "INSPECT", "BROWSER_ONLY"),
        machine_readable="HTML_ONLY",
        license_visibility="NOT STATED",
        reuse_policy="observation only",
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://www.cta.gallery",
        terms_notes="robots.txt Allow: /",
        verification_notes=(
            "CORRECTED HOST: ct.gallery does not resolve; the site is cta.gallery and requires www. "
            "549 sitemap locs. The main /cta page is a 5 MB single document, so sitemap plus per-entry "
            "fetching is the only sane retrieval"
        ),
        selection_notes="browser research. A 5 MB page is a fetch-cost argument, not an adapter argument",
    ),
    _source(
        "pricing-pages", "Pricing Pages", ("PRODUCT_PATTERN", "VISUAL_REFERENCE"),
        ("SEARCH", "INSPECT", "BROWSER_ONLY"),
        machine_readable="HTML_ONLY",
        license_visibility="NOT STATED. No terms page",
        reuse_policy="observation only",
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://pricingpages.com",
        terms_notes="robots.txt Allow: /",
        verification_notes=(
            "2,095 sitemap locs but a 6.4 MB root page. The site loads Figma's capture-to-design MCP "
            "script on every page -- that is THEIR build-time tool, not a public API for consumers, and "
            "wiring an adapter to it would be a category error"
        ),
        selection_notes="a legitimate PRODUCT_PATTERN source for pricing-page structure. Sitemap-driven only",
    ),
    _source(
        "hoverstates", "Hoverstat.es", ("MOTION_REFERENCE", "VISUAL_REFERENCE"),
        ("SEARCH", "INSPECT", "BROWSER_ONLY"),
        machine_readable="HTML_ONLY",
        license_visibility="NOT STATED",
        reuse_policy="observation only",
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://hoverstat.es",
        terms_notes="no published terms found",
        verification_notes=(
            "CORRECTED HOST: hoverstats.dev does not resolve, and neither does hoverstats.io. The real "
            "site is hoverstat.es (singular, .es)"
        ),
        selection_notes="the narrowest useful source here: hover and focus states only. Consult for an AFFORDANCE need",
    ),
    _source(
        "component-gallery", "Component Gallery", ("DESIGN_SYSTEM", "COMPONENT_PATTERN"),
        ("SEARCH", "INSPECT", "BROWSER_ONLY"),
        machine_readable="HTML_ONLY",
        license_visibility="Not licensed by the gallery; per-entry licensing follows the UPSTREAM project",
        reuse_policy=(
            "resolve each entry's licence from the upstream repository it links to, not from this site"
        ),
        adapter_status="BROWSER_RESEARCH_SOURCE",
        adapter_id="",
        endpoint="https://component.gallery",
        terms_notes="robots.txt Allow: /; no terms page",
        verification_notes=(
            "deliberately small: 66 sitemap locs, a curated set of real design-system components each "
            "linking to its upstream GitHub or Storybook. No API at any conventional path"
        ),
        selection_notes=(
            "the value is in following the OUTBOUND links to real upstream systems, not in the gallery "
            "itself. Per-entry upstream licence resolution is mandatory"
        ),
    ),
    # -- verified as dead, parked, or absorbed --------------------------------
    _source(
        "godly", "Godly", ("VISUAL_REFERENCE",), (),
        adapter_status="DISABLED", enabled=False,
        disabled_reason=(
            "the brand is gone. godly.website 301-redirects to recent.design, whose own info page "
            "states 'Recent also takes the place of Godly'. Retained so a legacy reference is not "
            "re-investigated"
        ),
        verification_notes="301 redirect confirmed on " + VERIFIED_ON,
    ),
    _source(
        "supahero", "Supahero", ("VISUAL_REFERENCE",), (),
        adapter_status="DISABLED", enabled=False,
        disabled_reason=(
            "absorbed. The homepage, nav and footer all announce 'supahero is now part of "
            "screensdesign'. Pricing is sponsorship-only with no consumer subscription, and the site "
            "returns 404 for robots.txt, sitemap.xml and llms.txt -- the only source here with zero "
            "discoverability files"
        ),
        verification_notes="post-acquisition notice observed on " + VERIFIED_ON,
    ),
    _source(
        "landing-love", "Landing Love", ("VISUAL_REFERENCE",), (),
        adapter_status="DISABLED", enabled=False,
        disabled_reason=(
            "DOWN. Name servers 109.68.33.62 and .63 do not respond (SERVFAIL via DNS-over-HTTPS). The "
            "domain resolves nowhere -- this is not a firewall, there is simply no server"
        ),
        verification_notes="SERVFAIL confirmed on " + VERIFIED_ON,
    ),
    _source(
        "scrolltide", "Scrolltide", ("MOTION_REFERENCE", "DESIGN_SYSTEM"), (),
        adapter_status="DISABLED", enabled=False,
        disabled_reason=(
            "not a product. The root redirects to /lander and serves a GoDaddy parking page "
            "(_trfd.push({ap:\"parking\"})). There is no gallery and no scroll tooling"
        ),
        verification_notes="domain parking confirmed on " + VERIFIED_ON,
    ),
    _source(
        "vibe-prompts", "Vibe Prompts", ("VISUAL_REFERENCE",), (),
        adapter_status="DISABLED", enabled=False,
        disabled_reason=(
            "the domain is for sale. 302-redirects to atom.com/name/VibePrompts behind a Cloudflare "
            "interstitial. The product no longer exists at this address"
        ),
        verification_notes="domain-for-sale redirect confirmed on " + VERIFIED_ON,
    ),
)

SOURCE_PROFILES: dict[str, dict] = {row["source_id"]: row for row in SOURCE_CATALOG}


def _profile(source_id: str) -> dict:
    row = SOURCE_PROFILES.get(str(source_id))
    if row is None:
        raise ContractError(
            f"unknown source {source_id!r}. A source may not be used unless the registry declares it"
        )
    return row


def source_problems(record: Mapping) -> list[str]:
    """Validate one profile. A registry entry that lies is worse than a missing one."""
    problems: list[str] = []
    if not str(record.get("source_id", "")).strip():
        problems.append("a source profile is named")
    if not str(record.get("display_name", "")).strip():
        problems.append("a source profile carries a display name")
    roles = record.get("source_roles")
    if not isinstance(roles, list) or not roles:
        problems.append("a source profile declares at least one role; a source can serve several")
    else:
        for role in roles:
            if str(role) not in SOURCE_ROLES:
                problems.append(f"unknown source role: {role!r}")
    capabilities = record.get("capabilities")
    if not isinstance(capabilities, list):
        problems.append("a source profile declares what Ariadne can actually do with it")
    else:
        for capability in capabilities:
            if str(capability) not in SOURCE_CAPABILITIES:
                problems.append(f"unknown source capability: {capability!r}")
    status = str(record.get("adapter_status", ""))
    if status and status not in ADAPTER_STATUS:
        problems.append(f"unknown adapter status: {status!r}")
    if record.get("enabled") is False and not str(record.get("disabled_reason", "")).strip():
        problems.append(
            "a disabled source states why. A source disabled without a reason will be "
            "re-enabled by someone who assumes the disabling was accidental"
        )
    if record.get("enabled") is False and record.get("paid_access"):
        problems.append(
            "a paid source cannot be enabled by default. Paid capability requires explicit "
            "authorization before use"
        )
    if status == "ADAPTER_AVAILABLE":
        if not str(record.get("adapter_id", "")).strip():
            problems.append("a source with an available adapter names the adapter")
        if "BROWSER_ONLY" in (record.get("capabilities") or []):
            problems.append(
                "a source marked BROWSER_ONLY cannot have an automated adapter. This is the exact "
                "contradiction that turns a browser-research source into a fabricated integration"
            )
        if not str(record.get("license_visibility", "")).strip():
            problems.append(
                "an adapter needs visible licence terms. An unknown licence is not a permissive one"
            )
    if not str(record.get("verification_notes", "")).strip():
        problems.append(
            "a source profile records what verification actually found. A registry entry with no "
            "verification note is a memory, and memories are how sources get misclassified"
        )
    return list(dict.fromkeys(problems))


def registry() -> dict:
    """The whole ecosystem, with its own integrity check run against itself."""
    problems: list[str] = []
    for row in SOURCE_CATALOG:
        problems.extend(f"{row.get('source_id', '?')}: {item}" for item in source_problems(row))
    return {
        "registry_id": "design-source-ecosystem-1",
        "sources": [dict(row) for row in SOURCE_CATALOG],
        "count": len(SOURCE_CATALOG),
        "roles": list(SOURCE_ROLES),
        "capabilities": list(SOURCE_CAPABILITIES),
        "adapter_statuses": list(ADAPTER_STATUS),
        "verified_at": VERIFIED_ON,
        "by_status": _by_status(),
        "problems": problems,
        "invariants": [
            "a registry entry is not an integration",
            "do not build thirty-six scrapers",
            "transport is not trust",
            "implementation sources are not aesthetic authority",
            "inspiration sources do not grant reuse rights",
        ],
    }


def _by_status() -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for row in SOURCE_CATALOG:
        grouped.setdefault(str(row.get("adapter_status", "")), []).append(str(row["source_id"]))
    return {key: sorted(value) for key, value in sorted(grouped.items())}


def enabled_sources() -> list[dict]:
    return [dict(row) for row in SOURCE_CATALOG if bool(row.get("enabled"))]


def adapter_sources() -> list[dict]:
    return [dict(row) for row in SOURCE_CATALOG if str(row.get("adapter_status")) == "ADAPTER_AVAILABLE"]


def by_role(role: str) -> list[dict]:
    if str(role) not in SOURCE_ROLES:
        raise ContractError(f"unknown source role: {role!r} (known: {', '.join(SOURCE_ROLES)})")
    return [dict(row) for row in SOURCE_CATALOG if role in (row.get("source_roles") or [])]


def by_capability(capability: str) -> list[dict]:
    if str(capability) not in SOURCE_CAPABILITIES:
        raise ContractError(f"unknown capability: {capability!r}")
    return [dict(row) for row in SOURCE_CATALOG if capability in (row.get("capabilities") or [])]


def unavailable_reason(source_id: str) -> str:
    """Why a source cannot be used right now. Empty means it is usable."""
    row = _profile(source_id)
    if not bool(row.get("enabled")):
        return str(row.get("disabled_reason", "")) or "this source is disabled"
    return ""


# ------------------------------------------------------- need-driven selection

EVIDENCE_NEEDS = (
    "COMPLETE_VISUAL_DIRECTION",
    "DATA_TABLE_PATTERNS",
    "LANDING_MOTION",
    "IMPLEMENTATION_PRIMITIVE",
    "SHADER_OR_GRAPHICS",
    "ASSET_ICON_OR_3D",
    "SPATIAL_3D_CAPABILITY",
    "MOTION_TIMELINE",
    "DESIGN_SYSTEM_TOKENS",
    "COMPONENT_LENS_EFFECT",
    "REAL_PRODUCT_FLOW_PATTERN",
)
"""What kind of evidence a need is asking for. Selection starts here, not with a list of sites."""

NEED_ROLES = {
    "COMPLETE_VISUAL_DIRECTION": ("DESIGN_SYSTEM", "VISUAL_REFERENCE"),
    "DATA_TABLE_PATTERNS": ("COMPONENT_PATTERN", "PRODUCT_PATTERN"),
    "LANDING_MOTION": ("MOTION_REFERENCE",),
    "IMPLEMENTATION_PRIMITIVE": ("IMPLEMENTATION_REGISTRY",),
    "SHADER_OR_GRAPHICS": ("TECHNICAL_CAPABILITY",),
    "ASSET_ICON_OR_3D": ("ASSET_SOURCE",),
    "SPATIAL_3D_CAPABILITY": ("TECHNICAL_CAPABILITY",),
    "MOTION_TIMELINE": ("TECHNICAL_CAPABILITY",),
    "DESIGN_SYSTEM_TOKENS": ("DESIGN_SYSTEM",),
    "COMPONENT_LENS_EFFECT": ("TECHNICAL_CAPABILITY", "IMPLEMENTATION_REGISTRY"),
    "REAL_PRODUCT_FLOW_PATTERN": ("PRODUCT_PATTERN",),
}
"""Which roles can answer which need.

The point of the map: "need data table patterns" is answered by component-pattern sources
and *not* by visual-reference sources, so a run that queries a gallery for table evidence
has asked the wrong question of the wrong corpus.
"""

NEED_BASIS = {
    "COMPLETE_VISUAL_DIRECTION": "a coherent system, not a set of screenshots",
    "DATA_TABLE_PATTERNS": "how real tabular content is arranged and labelled",
    "LANDING_MOTION": "motion with a recorded intent behind it",
    "IMPLEMENTATION_PRIMITIVE": "a primitive that supports the approved direction",
    "SHADER_OR_GRAPHICS": "shader work under a resolvable per-item licence",
    "ASSET_ICON_OR_3D": "assets whose licence permits the intended reuse",
    "SPATIAL_3D_CAPABILITY": "3D only when the direction's richness source asks for it",
    "MOTION_TIMELINE": "a timeline beyond what CSS expresses",
    "DESIGN_SYSTEM_TOKENS": "role-structured tokens from an inspected system",
    "COMPONENT_LENS_EFFECT": "a lens capability rather than an invented effect",
    "REAL_PRODUCT_FLOW_PATTERN": "how real products handle this specific flow, not how a gallery shows it",
}

MAX_SOURCES_PER_NEED = 3
"""A need consults a bounded number of sources.

Not a budget optimisation. Searching every source is the behaviour this exists to
prevent: it is slow, it drowns the useful evidence in the irrelevant, and -- most
importantly -- it makes "we consulted 30 sources" look like diligence when the honest
statement is "we did not know which two mattered".
"""


def _licence_established(row: Mapping) -> bool:
    visibility = str(row.get("license_visibility", "")).lower()
    if not visibility.strip():
        return False
    return not any(marker in visibility for marker in LICENCE_UNVERIFIED_MARKERS)


def _selection_rank(row: Mapping, matched_roles: Sequence[str]) -> tuple:
    """Prefer sources that can actually be used, then ones whose licence is established.

    Ranking rather than name order matters: alphabetically ``21st.dev`` precedes
    ``shadcn``, so an unordered sweep makes a metered, key-gated, per-component-licence
    source outrank a public MIT one. That is precisely the "did not know which two
    mattered" outcome the need-driven model exists to avoid.
    """
    status = str(row.get("adapter_status", ""))
    rank_status = {
        "ADAPTER_AVAILABLE": 0,
        "ADAPTER_VENDOR_KEY_REQUIRED": 1,
        "BROWSER_RESEARCH_SOURCE": 2,
        "REGISTRY_ONLY": 3,
        "DISABLED": 4,
    }.get(status, 5)
    rank_licence = 0 if _licence_established(row) else 1
    rank_auth = 0 if str(row.get("access_mode")) != "paid" else 1
    return (rank_status, rank_licence, rank_auth, -len(matched_roles))


def select_sources(
    need: str,
    *,
    limit: int = MAX_SOURCES_PER_NEED,
    registry_rows: Sequence[Mapping] | None = None,
    adapter_required: bool = False,
) -> dict:
    """Which sources would answer one need, and why -- and which were skipped, and why.

    The skip list is not filler. Recording *why* a capable source was not consulted is
    what makes the selection auditable, and it is what stops a run from drifting into
    query-everything while still looking thorough.
    """
    if str(need) not in EVIDENCE_NEEDS:
        raise ContractError(f"unknown evidence need: {need!r} (known: {', '.join(EVIDENCE_NEEDS)})")
    pool = list(registry_rows) if registry_rows is not None else list(SOURCE_CATALOG)
    roles = NEED_ROLES[need]
    selected: list[dict] = []
    skipped: list[dict] = []
    for row in sorted(pool, key=lambda item: str(item.get("source_id", ""))):
        source_id = str(row.get("source_id", ""))
        role_match = [role for role in roles if role in (row.get("source_roles") or [])]
        if not role_match:
            skipped.append({
                "source_id": source_id,
                "reason": f"serves {', '.join(row.get('source_roles') or [])}; this need wants {', '.join(roles)}",
                "role": "wrong-role",
            })
            continue
        if not bool(row.get("enabled")):
            skipped.append({
                "source_id": source_id,
                "reason": str(row.get("disabled_reason", "")) or "disabled",
                "role": "disabled",
            })
            continue
        if adapter_required and str(row.get("adapter_status")) != "ADAPTER_AVAILABLE":
            skipped.append({
                "source_id": source_id,
                "reason": (
                    f"status is {row.get('adapter_status')}, not ADAPTER_AVAILABLE. No adapter will "
                    "be built for it"
                ),
                "role": "no-adapter",
            })
            continue
        if str(row.get("access_mode")) == "paid":
            skipped.append({
                "source_id": source_id,
                "reason": "paid capability requires explicit authorization before use",
                "role": "paid-requires-authorization",
            })
            continue
        selected.append({
            "source_id": source_id,
            "display_name": str(row.get("display_name", "")),
            "matched_roles": role_match,
            "why": str(row.get("selection_notes", "")) or f"offers {', '.join(role_match)}",
            "adapter_status": str(row.get("adapter_status", "")),
            "license_visibility": str(row.get("license_visibility", "")),
            "reuse_policy": str(row.get("reuse_policy", "")),
            "_rank": _selection_rank(row, role_match),
        })
    selected.sort(key=lambda entry: (entry["_rank"], str(entry["source_id"])))
    selected = selected[: max(1, int(limit))]
    for entry in selected:
        entry.pop("_rank", None)
    considered = len(pool)
    return {
        "need": str(need),
        "basis": NEED_BASIS[str(need)],
        "roles_sought": list(roles),
        "sources_considered": considered,
        "sources_selected": [row["source_id"] for row in selected],
        "selected": selected,
        "skipped": skipped,
        "not_everything": True,
        "note": (
            f"{considered} registered sources were considered and {len(selected)} were selected. "
            "Consulting every source is not diligence; it is the absence of a question"
        ),
    }


def authority_check(source_id: str, *, direction_claims: str = "", rationale: str = "") -> dict:
    """Implementation registries are not aesthetic authority.

    The invariant:

    > **component exists on a registry != component should be used**

    and equally:

    > **an impressive effect != the product needs it**

    A registry may supply a primitive. It may not supply a decision. :func:`authority_check`
    refuses an adoption whose justification is the registry's existence rather than the
    approved direction.
    """
    row = _profile(source_id)
    claims = str(direction_claims or "").strip()
    reason = str(rationale or "").strip()
    registry_id = str(row.get("source_id", "")).lower()
    registry_name = str(row.get("display_name", "")).lower()
    merely_exists = bool(reason) and (
        registry_id in reason.lower() or registry_name in reason.lower()
    ) and not claims
    if merely_exists:
        return {
            "ok": False,
            "source_id": source_id,
            "problem": (
                f"the only justification recorded is that {row.get('display_name')} has it. A "
                "registry is a place to find primitives, not an authority on whether this product "
                "should use one"
            ),
            "required": (
                "name the approved-direction claim this primitive supports. A component earns its "
                "place by satisfying a requirement or a direction principle, never by being available"
            ),
        }
    if not reason:
        return {
            "ok": False,
            "source_id": source_id,
            "problem": "no adoption rationale was recorded",
            "required": "state the direction claim or requirement this primitive serves",
        }
    return {
        "ok": True,
        "source_id": source_id,
        "direction_claim": claims,
        "rationale": reason,
        "reuse_policy": str(row.get("reuse_policy", "")),
        "license_visibility": str(row.get("license_visibility", "")),
        "note": (
            "the primitive was selected because it serves a recorded claim. That is the whole test"
        ),
    }


PROHIBITED_USE_PROBES = (
    (
        "training or dataset construction",
        ("train", "training", "fine-tune", "finetune", "model training", "dataset", "search index",
          "design index", "competing index", "build an index", "corpus", "benchmark", "evaluat"),
        ("train", "fine-tune", "dataset", "index", "benchmark", "machine learning", "model"),
    ),
    (
        "republication",
        ("republish", "resell", "redistribute", "sublicense", "syndicate", "sell"),
        ("republish", "resell", "redistribut", "sublicens", "syndicat", "marketplace", "sell"),
    ),
    (
        "bulk mirroring",
        ("mirror", "bulk download", "bulk scrape", "bulk harvest", "bulk", "crawl", "harvest"),
        ("mirror", "bulk", "crawl", "scrap", "harvest", "overload"),
    ),
    (
        "automated scraping",
        ("scrape", "scraping", "web scraping", "automated collection", "bot", "crawler"),
        ("scrap", "automated means", "bot", "crawler", "collect"),
    ),
    (
        "verbatim copying",
        ("copy code", "copy the composition", "copy composition", "reproduce layout",
         "clone composition", "copy asset", "copy brand", "verbatim", "replicate design",
         "extract component", "source code", "redistribute", "re-distribute", "republish"),
        ("reproduc", "verbatim", "copy", "clone", "replicate", "extract", "redistribut",
         "republish"),
    ),
    (
        "access control circumvention",
        ("bypass", "circumvent", "without api key", "without an account", "without a licence",
         "without an api key", "unauthenticated", "skip the paywall", "no account",
         "free tier instead of", "share an api key"),
        ("circumvent", "payment", "access control", "rate limit", "bypass", "licence", "account",
         "token"),
    ),
    (
        "impersonation",
        ("impersonate", "pretend to be", "act as the brand", "pose as"),
        ("impersonat", "pretend", "act as"),
    ),
)
"""Activity phrases that trip a prohibition, paired with the words a prohibition uses.

Two lists rather than one, because matching only against the *prohibition* text depends on
how it happened to be worded. Writing "use Refero results to build a design index" against
a prohibition that reads *"creating datasets, benchmarks or a competing product or search
index"* needs the noun list; catching *"scrape the getdesign site"* against *"automated
scraping of the site"* needs the verb list. The prohibition decides *whether* a category
applies; the activity decides *whether this run* tripped it. Requiring both is what makes
the check usable on prose written by two different people.
"""


def _prohibited_use_matches(source_id: str, use: str) -> list[dict]:
    row = _profile(source_id)
    recorded = [str(item).lower() for item in (row.get("prohibited_uses") or [])]
    if not recorded:
        return []
    activity = " ".join(str(use or "").lower().split())
    hits: list[dict] = []
    for kind, activity_probes, prohibition_markers in PROHIBITED_USE_PROBES:
        matched = [probe for probe in activity_probes if probe in activity]
        if not matched:
            continue
        applicable = [
            prohibition for prohibition in recorded
            if any(marker in prohibition for marker in prohibition_markers)
        ]
        if applicable:
            hits.append({"kind": kind, "matched": matched, "recorded_prohibition": applicable})
    return hits


def reuse_check(source_id: str, *, use: str) -> dict:
    """Inspiration does not grant reuse rights.

    A visual or reference source informs hierarchy, rhythm, interaction and composition. It
    does not license copying source code, branded assets, or an exact composition -- and the
    failure is always the same one: an adapter that was built to read a reference gallery
    ends up reproducing a layout from it.

    This also refuses the recorded ``prohibited_uses`` of each source, which is where the
    Refero terms land: model training, dataset construction and competing-index creation are
    prohibited there *even for paying customers*, so a run that treats paid access as blanket
    permission is the exact bug this check exists to catch.
    """
    row = _profile(source_id)
    activity = " ".join(str(use or "").lower().split())
    if not bool(row.get("enabled")):
        return {
            "ok": False,
            "source_id": source_id,
            "problem": (
                f"{row.get('display_name')} is disabled: "
                f"{row.get('disabled_reason', '') or 'this source is disabled'}"
            ),
            "required": "use a source the registry declares usable, or record why this one is needed",
        }
    violations = _prohibited_use_matches(source_id, activity)
    if violations:
        return {
            "ok": False,
            "source_id": source_id,
            "problem": (
                f"the recorded use {use!r} matches an activity this source's terms prohibit for "
                + "; ".join(str(item["recorded_prohibition"][0]) for item in violations)
            ),
            "violations": violations,
            "note": (
                "paid access is not blanket permission. A paying customer can still be inside a "
                "prohibition, and paying does not buy the right to train, benchmark or republish"
            ),
            "required": "refuse the use, or restrict the source to observation of its principles",
        }
    reference_only = ("VISUAL_REFERENCE" in (row.get("source_roles") or [])) and (
        "IMPLEMENTATION_REGISTRY" not in (row.get("source_roles") or [])
    )
    # The same probe vocabulary the prohibition check uses. A second, narrower list here is how
    # "copy the composition" passed while "clone composition" was caught -- two phrasings of one
    # activity, two different answers, both from the same function.
    copying = any(
        probe in activity
        for _kind, probes, _markers in PROHIBITED_USE_PROBES
        if _kind == "verbatim copying"
        for probe in probes
    )
    if reference_only and copying:
        return {
            "ok": False,
            "source_id": source_id,
            "problem": (
                f"{row.get('display_name')} is a visual reference, and the recorded use is "
                f"{use!r}. A reference may inform hierarchy, rhythm and composition. It does not "
                "grant rights to source code, branded assets or an exact composition"
            ),
            "permitted": "record the principles observed and implement them independently",
        }
    visibility = str(row.get("license_visibility", ""))
    unverified = any(token in visibility.lower() for token in LICENCE_UNVERIFIED_MARKERS)
    if unverified:
        return {
            "ok": False,
            "source_id": source_id,
            "problem": (
                f"{row.get('display_name')}'s licence is not established: {visibility}. An unknown "
                "licence is not a permissive one"
            ),
            "required": "resolve the licence from a primary source, or record the material as evidence only",
        }
    return {
        "ok": True,
        "source_id": source_id,
        "use": str(use),
        "license_visibility": visibility,
        "prohibitions_considered": list(row.get("prohibited_uses") or []),
    }


def selection_economics(selections: Sequence[Mapping], *, bytes_by_source: Mapping | None = None,
                        seconds_by_source: Mapping | None = None) -> dict:
    """Source economics, recorded in the Context Economics shape AR-204 established."""
    sizes = bytes_by_source if isinstance(bytes_by_source, Mapping) else {}
    times = seconds_by_source if isinstance(seconds_by_source, Mapping) else {}
    rows: list[dict] = []
    total_bytes = 0
    total_seconds = 0.0
    considered = 0
    skipped = 0
    for selection in selections or ():
        if not isinstance(selection, Mapping):
            continue
        considered = max(considered, int(selection.get("sources_considered", 0) or 0))
        skipped += len(selection.get("skipped") or [])
        for entry in selection.get("selected") or []:
            if not isinstance(entry, Mapping):
                continue
            source_id = str(entry.get("source_id", ""))
            moved = int(sizes.get(source_id, 0) or 0)
            elapsed = float(times.get(source_id, 0.0) or 0.0)
            total_bytes += moved
            total_seconds += elapsed
            rows.append({
                "source_id": source_id,
                "need": str(selection.get("need", "")),
                "why_selected": str(entry.get("why", "")),
                "bytes_transported": moved,
                "seconds": elapsed,
                "deep_inspected": moved > 0,
            })
    return {
        "needs": [str(row.get("need", "")) for row in (selections or []) if isinstance(row, Mapping)],
        "sources_considered": considered,
        "sources_queried": sum(1 for row in rows if row["deep_inspected"]),
        "sources_skipped_with_reason": skipped,
        "candidates": len(rows),
        "deep_inspections": sum(1 for row in rows if row["deep_inspected"]),
        "bytes_transported": total_bytes,
        "seconds": round(total_seconds, 3),
        "rows": rows,
        "stopped_because": (
            "enough evidence existed for each recorded need; further queries would add bytes without "
            "adding a decision"
        ),
        "shape": (
            "sources considered, sources queried, why selected, why skipped, candidates, deep "
            "inspections, bytes transported, time"
        ),
    }


def capability_claims_match_reality(source_id: str, *, claimed: Mapping | None = None) -> dict:
    """Provider metadata that lies about capability is a contradiction, not a fact.

    The brief's requirement is that capabilities describe what Ariadne can actually do, not
    what a marketing page claims. A registry entry asserting an API it does not have -- or
    a browser-only source marked API-capable -- is refused here so the contradiction
    surfaces at the boundary rather than at the point of a failed fetch.
    """
    row = _profile(source_id)
    stated = list(row.get("capabilities") or [])
    if not claimed:
        return {"ok": True, "source_id": source_id, "capabilities": stated, "contradiction": ""}
    asserted = [str(item) for item in (claimed.get("capabilities") or [])]
    unsupported = [
        capability for capability in asserted
        if capability not in stated
    ]
    contradiction = ""
    if "API" in asserted and "BROWSER_ONLY" in stated:
        contradiction = (
            "the provider claims an API while the registry records BROWSER_ONLY. A browser-only "
            "source does not have an API; whichever is wrong, the source cannot be relied on"
        )
    if "COMPONENT_CODE" in asserted and "COMPONENT_CODE" not in stated:
        contradiction = "the provider claims component code retrieval that the registry does not record"
    if "DOWNLOAD" in asserted and bool(row.get("paid_access")) and not claimed.get("authorized"):
        contradiction = (
            "download asserted against a paid source without recorded authorization"
        )
    return {
        "ok": not contradiction and not unsupported,
        "source_id": source_id,
        "recorded": stated,
        "asserted": asserted,
        "unsupported_assertions": unsupported,
        "contradiction": contradiction,
        "access_mode": str(row.get("access_mode", "")),
        "paid_access": bool(row.get("paid_access")),
        "invariant": "transport is not trust; a source cannot certify its own capability",
    }


def describe(source_id: str) -> str:
    row = _profile(source_id)
    reason = unavailable_reason(source_id)
    state = "enabled" if row.get("enabled") else f"DISABLED ({reason})"
    return (
        f"{row.get('display_name')} [{state}]: roles {', '.join(row.get('source_roles') or [])}; "
        f"status {row.get('adapter_status')}; access {row.get('access_mode')}"
        f"{' (paid)' if row.get('paid_access') else ''}; "
        f"licence {row.get('license_visibility') or 'not stated'}"
    )


__all__ = [
    "ACCESS_MODES",
    "ADAPTER_STATUS",
    "EVIDENCE_NEEDS",
    "MAX_SOURCES_PER_NEED",
    "NEED_BASIS",
    "NEED_ROLES",
    "SOURCE_CAPABILITIES",
    "SOURCE_CATALOG",
    "SOURCE_PROFILES",
    "SOURCE_ROLES",
    "VERIFIED_ON",
    "adapter_sources",
    "authority_check",
    "by_capability",
    "by_role",
    "capability_claims_match_reality",
    "describe",
    "enabled_sources",
    "registry",
    "reuse_check",
    "select_sources",
    "selection_economics",
    "source_problems",
    "unavailable_reason",
]
