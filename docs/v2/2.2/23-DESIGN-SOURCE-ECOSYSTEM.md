# 23 — Design Source Ecosystem

> **A registry entry is not an integration.**

## The failure this prevents

It is trivially easy to produce a list of thirty-six design sources and call it an
ecosystem. Doing so is *worse* than having no list, because the list then reads as
thirty-six integrations.

The honest answer, verified on 2026-10-05:

```text
39 sources registered
10 with a defensible automated path
 2 requiring a vendor key
16 browser-research only
 4 record-only (licence forbids redistribution, or frozen)
 7 disabled (verified absent, parked, absorbed or non-existent)
```

That gap is the point. It is recorded per source rather than smoothed over by building
thirty-six scrapers.

## Verified before classified

Every entry was inspected against its live public surface. `verification_notes` records what
verification actually found, and a profile without one is refused:

```text
a source profile records what verification actually found. A registry entry with no
verification note is a memory, and memories are how sources get misclassified.
```

Verification frequently contradicted the marketing page. The findings that mattered:

| Finding | Consequence |
|---|---|
| `ui.shadcn.com/r/registries.json` is a public **418-entry registry directory** | shadcn is the substrate every other registry resolves through |
| Magic UI, Motion Primitives, SmoothUI, Microkit, Aceternity all serve shadcn-spec JSON **with no login** | five "copy-paste" sites are machine-readable after all |
| **Refero §10/§13 prohibit model training, dataset creation and competing indexes — for paying MCP users too** | Refero is research-only; paid access is not blanket permission |
| **The Book of Shaders is ALL RIGHTS RESERVED**, not the CC BY-NC-SA widely assumed | an assumed licence is a legal claim, and it was wrong |
| **21st.dev ToS §3 forbids scraping *and* republishing metadata by any means** | sanctioned API only; never scrape, never harvest metadata |
| minimal.gallery `robots.txt` is permissive but its `/legal` page names scraping prohibited | **terms control where the two disagree** |
| designmd.ai `robots.txt` says `Disallow: /api/` while its own CLI calls `/api/v1/` | official clients only, never a bespoke HTTP client |
| Aceternity returns **401 for unknown items** — a soft-404, not a paywall | existence checks cannot distinguish "unknown" from "gated" |
| Microkit's MIT is *asserted by a directory listing*, with no licence page and no repo | `REGISTRY_ONLY` until confirmed from a primary source |

### Sources that do not exist

Recorded as `DISABLED` with a reason, rather than deleted — a source that stopped existing is
a finding, and deleting it means the next person re-investigates:

```text
kinetics       NXDOMAIN (kinetics.nexxt.ai; nexxt.ai is an unrelated consultancy)
kitbitz        GoDaddy parking page; a sitemap containing exactly one URL
landinglove    nameservers do not respond (SERVFAIL) -- no server at all
scrolltide     parked domain; no gallery and no scroll tooling
vibeprompts    for sale at atom.com/name/VibePrompts
godly          rebranded to recent.design; "Recent also takes the place of Godly"
supahero       absorbed into screensdesign; no robots, no sitemap, no llms.txt
```

Four hostnames in the phase brief were also wrong: `hoverstats.dev` → **hoverstat.es**,
`navbars.gallery` → **navbar.gallery**, `ct.gallery` → **cta.gallery**,
`glass.samasante` → **`@samasante/liquid-glass`**.

## Roles and capabilities

```text
roles         DESIGN_SYSTEM · VISUAL_REFERENCE · PRODUCT_PATTERN · COMPONENT_PATTERN ·
              IMPLEMENTATION_REGISTRY · MOTION_REFERENCE · ASSET_SOURCE · TECHNICAL_CAPABILITY
capabilities  SEARCH · INSPECT · DESIGN_MD · SCREENSHOTS · VIDEO · COMPONENT_CODE ·
              MCP · CLI · API · BROWSER_ONLY · DOWNLOAD
statuses      ADAPTER_AVAILABLE · ADAPTER_VENDOR_KEY_REQUIRED · REGISTRY_ONLY ·
              BROWSER_RESEARCH_SOURCE · DISABLED
```

Role drives selection: "I need data-table patterns" is a `COMPONENT_PATTERN` need, and no
amount of `MOTION_REFERENCE` evidence answers it.

`API`/`MCP`/`CLI` describe a **stable documented** mechanism, not an HTTP endpoint that
happens to answer. `BROWSER_ONLY` is an honest capability rather than a missing one.

`ADAPTER_VENDOR_KEY_REQUIRED` is separate from `ADAPTER_AVAILABLE` because "there is a
documented API" and "you may use it right now" are different facts, and conflating them is
how an unauthenticated free tier becomes an assumed capability.

`REGISTRY_ONLY` is the interesting status: the source *is* machine-readable, but its licence
forbids the redistribution an adapter would perform, or the catalogue is frozen. Recording it
as an available integration would be the lie this taxonomy exists to stop — which is why
`source_problems()` refuses a profile that claims `ADAPTER_AVAILABLE` while also declaring
`BROWSER_ONLY`.

## Need-driven selection

Eleven evidence needs (`sources.EVIDENCE_NEEDS`), each mapped to the roles that can answer
it. A run states what kind of evidence it needs; the registry decides who to ask.

```text
DATA_TABLE_PATTERNS         -> COMPONENT_PATTERN, PRODUCT_PATTERN
COMPLETE_VISUAL_DIRECTION   -> DESIGN_SYSTEM, VISUAL_REFERENCE
LANDING_MOTION              -> MOTION_REFERENCE
IMPLEMENTATION_PRIMITIVE    -> IMPLEMENTATION_REGISTRY
SHADER_OR_GRAPHICS          -> TECHNICAL_CAPABILITY
REAL_PRODUCT_FLOW_PATTERN   -> PRODUCT_PATTERN
```

Selection is bounded (`MAX_SOURCES_PER_NEED = 3`), ranked by usability rather than name, and
**records why each capable source was skipped**. The skip list is not filler: it is what makes
the selection auditable, and what stops a run drifting into query-everything while still
looking thorough.

Name-order ranking was a real bug the adversarial suite found: alphabetically `21st.dev`
precedes `shadcn`, so an unordered sweep made a metered, key-gated, per-component-licence
source outrank a public MIT one. That is precisely the *"we did not know which two mattered"*
outcome need-driven selection exists to avoid.

## Four invariants, enforced

**Do not build thirty-six scrapers.** An adapter requires a public documented API, public MCP,
public CLI, public repository, explicit machine-readable feed, or permitted deterministic
browser access. Everything else stays browser-research or disabled.

**Transport is not trust.** MCP, CLI and browser content is external data.
`capability_claims_match_reality()` refuses provider metadata that contradicts the registry:

```text
the provider claims an API while the registry records BROWSER_ONLY. A browser-only source
does not have an API; whichever is wrong, the source cannot be relied on
```

**Implementation sources are not aesthetic authority.**

> component exists on a registry ≠ component should be used

`authority_check()` refuses an adoption whose only justification is that a registry has it, and
refuses one with no rationale at all.

**Inspiration does not grant reuse rights.** A reference informs hierarchy, rhythm, interaction
and composition. `reuse_check()` refuses copying source code, branded assets or an exact
composition from a `VISUAL_REFERENCE`-only source, and consults each source's recorded
`prohibited_uses` — matched structurally, so a prohibition written as prose actually bites:

```text
the recorded use 'train a model on Refero screenshots' matches an activity this source's
terms prohibit for training, fine-tuning, evaluating or improving machine learning models
or datasets

paid access is not blanket permission. A paying customer can still be inside a prohibition,
and paying does not buy the right to train, benchmark or republish
```

`Book of Shaders` is the sharpest case: widely assumed CC BY-NC-SA, actually all-rights-reserved,
and `reuse_check` refuses it on the recorded licence.

## DESIGN.md providers stay distinct

Three providers of DESIGN.md-shaped material, three identities:

```text
getdesign          the AR-220 corpus path, preserved unchanged (74 frozen fixtures, offline)
awesome-design-md  the GitHub repository and npm CLI -- MIT, offline-capable, the licence-clean
                   channel, because the directory's ToS bans scraping the site while permitting
                   use of the artefacts
designmd-ai        421 kits, own licence model, own robots conflict
```

Collapsing them into one entry would hide exactly the licence differences that matter.

## Economics

`selection_economics()` records the AR-204 shape: sources considered, sources queried, why
selected, why skipped, candidates, deep inspections, bytes transported, time — and
`stopped_because`. The F1 slice: **5 needs, 14 selections of 39 registered sources, 5 deep
inspections, 18 KB, ~12 s.**

## See also

- [26 — Harness Integrity](26-HARNESS-INTEGRITY.md)
- [27 — Adversarial Review](27-ADVERSARIAL-REVIEW.md)
- [28 — AR-222D Results](28-AR-222D-RESULTS.md)
