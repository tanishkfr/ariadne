# 01 — Grounded Design Intelligence (AR-220)

> **References are evidence, not authority.**
> **Observed is not recommended. Recommended is not approved.**
> **MCP and CLI are transports, not trust.**
> **getdesign.md is a useful curated source, not ground truth.**
> **Project identity comes before external inspiration.**
> **Ariadne should retrieve enough reference evidence to justify the design — then stop searching.**

## What this phase is

AR-220 is the **foundation of pillar 2** of Ariadne 2.2: Grounded Design
Intelligence. It builds the reference/evidence substrate that a design workflow
needs in order to answer

> **Why did you choose this design?**

with an answer a reviewer can audit, rather than an answer that amounts to "three
websites looked similar".

It is not a redesign of Ariadne, not a GUI, not a trained Decision Runtime, and
not a browser scraper. It is the layer that makes the *next* phase's work
verifiable: if reference acquisition and evidence assembly are themselves
inspected, then a rendered critique in AR-221 can be grounded in something real.

## The gap this fills

Ariadne 2.1 already had a reference record family. It was genuinely good at the
part it answered:

```text
FOUND → ACCESSIBLE → INSPECTED → ANALYSED → USED
```

with adapters that run only under declared capabilities, digests on every
retrieval, local artifacts re-hashed against the project root, and design
direction that cites references by id.

What it could not answer was *which kind of evidence it was holding*. A curated
third-party analysis of a design system and that vendor's own published design
system were both "a reference". They were not the same thing, and the record
said nothing about the difference. So a direction could cite three references and
carry no information about whether any of them deserved the citation.

The classification is the substance of AR-220, and it is what gives a reference meaning:

| Question | Before | After |
|----------|--------|-------|
| What kind of source was this? | — | `source_kind`, 10 values |
| How was it actually obtained? | lifecycle implied it | `evidence_level`, 6 values |
| May we read it at all? | refused or not attempted | `access_mode`, incl. `ACCESS_RESTRICTED` |
| Is it current? | retrieved timestamp only | `freshness` + change detection |
| What did we actually observe? | free-text findings | controlled `observed_patterns` |
| How may it be used? | — | `BORROW` / `ADAPT` / `AVOID` |

## The six-step flow

```text
understand the design need
        ↓
identify what reference evidence is missing
        ↓
find real references                     ← acquisition order, one adapter per source
        ↓
retrieve and inspect them                ← targeted retrieval, authorized fetch only
        ↓
normalize into provenance-backed records ← DesignReference
        ↓
construct a deliberate reference set      ← ReferenceSet + counter-references
        ↓
extract design principles                ← corroborated by ≥2 independent sources
        ↓
form a design direction                   ← every major choice cites its evidence
```

Each step is implemented, and each step's *refusal* is as real as its success.

## Module map

| Module | Responsibility |
|--------|----------------|
| `safety.py` | SSRF, containment, prompt-injection scanning, resource bounds |
| `designmd.py` | `DESIGN.md` as an **input format** (bounded YAML subset, no dependency) |
| `normalize.py` | raw bytes → one provider-neutral `DesignReference` |
| `getdesign.py` | the getdesign.md adapter — the only site-aware module |
| `discovery.py` | project-local evidence, examined *before* anything external |
| `sets.py` | `ReferenceSet`: roles, counter-references, diversity, budget |
| `transports.py` | MCP and CLI boundaries that are transports, not trust |
| `direction.py` | the grounded design-direction compiler |
| `acquire.py` | search → candidate → fetch → normalize → register |
| `vertical_slice.py` | the end-to-end AR-220 vertical slice |

## Architecture requirement: sources are swappable

Section 35 of the AR-220 brief requires that this future flow work **without
changing `DesignReference`**:

```text
Ariadne reference need
      ↓
project DESIGN.md          → LOCAL_DESIGN_FILE
      ↓
Figma MCP                 → MCP_RESULT
      ↓
getdesign.md              → CURATED_DESIGN_ANALYSIS
      ↓
GitHub source             → SOURCE_REPOSITORY
      ↓
component CLI             → CLI_RESULT
```

This is enforced by shape, not by intent:

- `normalize.normalize_reference()` is the only path from bytes to a record, and it
  takes `source_kind` from the adapter that performed the retrieval;
- every transport payload passes through `safety.as_data_only` and
  `safety.scan_reference_text` before it is stored;
- a transport that is absent is a valid adapter
  (`UnavailableMCPAdapter`) that reports its own reason, so adding a source means
  adding an adapter, never changing the record.

## Permanent invariants, and where they are enforced

| Invariant | Enforced by | Mutation test |
|-----------|-------------|---------------|
| A curated analysis is not first-party | `getdesign.SOURCE_KIND` is a constant; validator rejects unknown kinds | `curated analysis promoted to first-party` |
| Observed ≠ recommended | `sets.assert_observation_not_recommendation`; `GENERIC_GROUNDING_BLOCKERS` | `one source claims SUPPORTED` |
| Recommended ≠ approved | compiler emits `CANDIDATE`; `grounding_problems` rejects anything else | `compiled direction self-approves` |
| Reference text is data | `safety.scan_reference_text` records, never obeys | `reference text treated as authorisation` |
| MCP/CLI grant no authority | `validate_argv`, `requires_authorization`, `probe()` | `retrieval allowlist requires every prefix` |
| No public access bypass | `require_fetchable_url`; gated content recorded `ACCESS_RESTRICTED` | `access-restricted download treated as public` |
| Project first | `external_reference_worthwhile` refuses before local probes run | `project-first order inverted` |
| Bounds hold | `sets.spend` refuses before incrementing | `reference budget ignored` |
| Records bind to content | content digest + normalised digest | `reference digest omitted` |
| Evidence is reproducible | frozen fixtures; no network in the suite | — |

## The vertical slice

`vertical_slice.py` answers one request end to end, offline and deterministically:

> Ask for a direction for a serious desktop developer tool that feels precise,
> dense and calm, while explicitly not reading as a generic AI dashboard.

Result: **5 references** (the project's own `DESIGN.md` plus 4 curated analyses
including Cohere as the counter-reference), **12 extracted principles**, a
`CANDIDATE` direction with **no ungrounded sections**, and **67 BORROW/ADAPT/AVOID
treatments**. Full numbers in [08-AR-220-RESULTS.md](08-AR-220-RESULTS.md).

The slice stops at **approved-ready design direction evidence**. It renders
nothing, implements no UI and critiques nothing.

## What is deliberately not here

- **No vector database, no embeddings.** Search is deterministic lexical matching
  over a declared vocabulary. An unauditable relevance function is worse than an
  honest one that admits it is lexical.
- **No mandatory network, MCP, Node or CLI.** All four are optional transports; the
  capability matrix says so and the offline path is tested.
- **No automatic broad search.** There is no "search until satisfied" loop.
  Sufficiency is a caller decision, because only the caller knows what would
  satisfy it.
- **No UI implementation.** AR-221 owns execution and reference-aware critique.

## Read next

- [02-REFERENCE-CONTRACT.md](02-REFERENCE-CONTRACT.md) — the record and its invariants
- [03-GETDESIGN-MD-AUDIT.md](03-GETDESIGN-MD-AUDIT.md) — what the live site actually exposes
- [04-DESIGN-MD-FORMAT.md](04-DESIGN-MD-FORMAT.md) — the input format and what we consume
- [05-MCP-AND-CLI-ADAPTERS.md](05-MCP-AND-CLI-ADAPTERS.md) — transports, not trust
- [06-REFERENCE-SECURITY.md](06-REFERENCE-SECURITY.md) — the attack surface and its refusals
- [07-REFERENCE-ECONOMICS.md](07-REFERENCE-ECONOMICS.md) — budgets, telemetry, change detection
- [08-AR-220-RESULTS.md](08-AR-220-RESULTS.md) — measured results and honest limitations