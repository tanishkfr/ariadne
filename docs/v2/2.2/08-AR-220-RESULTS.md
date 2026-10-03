# 08 — AR-220 Results (AR-220)

Measured results for the Grounded Design Intelligence foundation. Every number
below was produced by running the code in this branch; nothing is projected.

**Status: AR-220 COMPLETE WITH KNOWN LIMITATIONS** — see §20 for the honest list.

## 1. Repository

| Item | Value |
|------|-------|
| Worktree | `C:\Dev\Tools\Ariadne\ariadne-v2-2-grounded-design` |
| Branch | `v2/2.2-grounded-design-intelligence` |
| Base | `aba1f89834ea64a30c527f520125294f3f058068` |
| `v2.1.0` tag | `70e203c91ac56d3611eac3aed22491b1c7bac41b` — **unmodified** |
| `v2.1.0rc1` tag | `beb0e1c` — **unmodified** |
| `VERSION` | `2.1.0` — **deliberately unchanged**, see §21 |

The base is `aba1f89`, the 2.1 release-branch HEAD that records the stable release,
rather than the `v2.1.0` tag `70e203c` directly. `aba1f89` is a strict superset of
the tag: it adds the release-record documentation and no code change. Neither the
tag nor `v2.1.0rc1` was rewritten.

## 2. Baseline

Reproduced before any edit, then re-verified after every change.

| Suite | 2.1 baseline | After AR-220 |
|-------|-------------|--------------|
| `test-engine-core.py` | 578/578 | **578/578** |
| `test-decision-runtime.py` | 510/510 | **510/510** |
| `test-decision-mutations.py` | 9/9 | **9/9** |
| `test-decision-runtime-mutations.py` | 38/38 | **38/38** |
| `test-release.py` | 97/97 | **97/97** |
| `test-distribution.py` | 55/55 | **55/55** |
| `check.py` | PASS | **PASS** |
| `release-check.py` | **12/12** | **12/12** (1 `NOT_EXECUTED`: artifacts not built in a dev worktree) |
| `benchmarks/run_benchmarks.py --release` | 79/79 | **79/79** |

### A baseline failure that was environmental, not a defect

Running the gate inside the **2.1 worktree** first produced 2 failures:

```text
repository contract          FAILED  3784 duplicated sentences
release benchmark subset     FAILED  78 pass, 1 fail  (suite.repo-contract)
```

Root cause: the Agent Manager worktree `.kilo/worktrees/plain-sarahsaurus` is nested
*inside* the 2.1 checkout. It is untracked and excluded via `.git/info/exclude`, so
git reports the tree clean — but `check.py`'s duplicate-sentence scan walks the
filesystem and found a complete duplicate Ariadne checkout inside it. Both failures
had one cause, and neither was a 2.1 code defect: `v2.1.0` shipped green at
`70e203c`, before that nested worktree existed. The clean 2.2 worktree has no such
contamination and reports **12/12**.

`EXCLUDED_SCAN_DIRS` was **not** extended to hide it, because doing so would have
masked a real class of problem for future worktrees.

## 3. Existing Design Intelligence audit

What AR-220 inherited, and what was therefore extended rather than replaced.

| Capability | Existed in 2.1 | Reused? |
|------------|----------------|---------|
| Reference lifecycle `FOUND → ACCESSIBLE → INSPECTED → ANALYSED → USED` | yes | **yes** — unchanged |
| Reference adapters with declared capabilities and authorisation | yes | **yes** — getdesign.md implements the same contract |
| Recursive-suffix safety on reference adapters | yes | **yes** — the new adapter honours it |
| Content digest on every retrieval | yes | **yes** — extended with a normalised-record digest |
| Local artifact re-hashing against the project root | yes | **yes** — project-local documents re-hashed |
| Design direction with `G1D` approval | yes | **yes** — the compiler emits `CANDIDATE` only |
| Design Intelligence measures (depth, coverage, provenance) | yes | **yes** — extended with reference lines |
| Context Economics (`economics.py`) | yes | **yes** — reference budgets join it |
| Canonical events | yes | **yes** — AR-220 rides existing event infrastructure |
| **Source classification** | **no** | **new** |
| **Evidence level** | **no** | **new** |
| **Reference set with roles** | **no** | **new** |
| **Counter-references** | **no** | **new** |
| **Diversity verdict** | `diversity_notes` prose only | **new, deterministic** |
| **Normalised observation vocabulary** | **no** | **new** |
| **BORROW / ADAPT / AVOID** | **no** | **new** |
| **Content digest of the normalised record** | **no** | **new** |

Deliberately **not** built: a trained Decision Runtime, a GUI, a browser scraper, a
vector database, mandatory paid services.

## 4. getdesign.md audit

Full detail in [03-GETDESIGN-MD-AUDIT.md](03-GETDESIGN-MD-AUDIT.md). Findings that
changed the design:

1. **550+ entries**, not the 300+ the brief expected; 764 sitemap URLs.
2. **Slugs are host-like** — `linear.app`, `x.ai`, `cal`, `runwayml`, `bmw-m`,
   `dell-1996` — so a slug can never be derived from a brand name.
3. **The raw `DESIGN.md` is not publicly downloadable from the catalog.** The
   download control is sign-in gated behind Catalog Pass. Four plausible raw paths
   all returned 404; `/design-md/{slug}/preview.html` is public and carries real
   CSS custom properties.
4. **The Terms of Service prohibit automated scraping** (section 7), while
   `robots.txt` permits the catalog. The Terms are the tighter constraint and
   govern: no crawling, no sitemap walking, no link following, targeted
   single-file retrieval only, and an operator-supplied authorized fetch
   capability is **required**.
5. **The raw documents are public and MIT-licensed** in
   `VoltAgent/awesome-design-md` — the path the maintainers publish for agents.
   That is what Ariadne reads.
6. **Every audited entry carries a first-party disclaimer** and records
   `catalog_raw_download_gated: true`. getdesign.md says it is independent analysis
   and not an official design system, so `source_kind` is a constant in the adapter.

## 5. The separate `getdesign` project

`MohtashashMurshid/getdesign` (MIT) is a **different project**: on-demand extraction
from any URL. Verified state — web implemented, agent skill implemented, **HTTP API
planned**, **CLI placeholder**, **SDK placeholder**.

- **No code copied. No code adapted.** MIT permits reuse; none was needed.
- Studied: the documented 9-section contract, the grounding-in-inspected-CSS
  principle, token extraction concepts, screenshot requirements, anti-hallucination
  stance.
- Adopted as **principles**, reimplemented independently.
- **No API call, SDK import or CLI invocation exists in this codebase.**
- Ariadne does not brand itself "getdesign mode" or as "powered by" either project.

## 6. DesignReference

10 source kinds, 6 evidence levels, 4 access modes, 5 freshness states, 7 roles, 3
treatments, 16 observation dimensions. Full contract in
[02-REFERENCE-CONTRACT.md](02-REFERENCE-CONTRACT.md).

Invariants, each with a mutation test:

| Invariant | Caught by mutation |
|-----------|-------------------|
| A curated analysis is never first-party | `curated analysis promoted to first-party` |
| Every record binds to content bytes | `reference digest omitted` |
| Reference text grants no authority | `reference text treated as authorisation` |
| Observations are not instructions | `one source claims SUPPORTED` |
| Motion requires a declared basis | `motion observed without a basis` |
| Restricted content is never parsed | tested directly |

## 7. ReferenceSet

Roles, counter-references, deterministic diversity, enforced budget.

| Property | Value |
|----------|-------|
| Members | 5 |
| Roles held | `PRIMARY_DIRECTION` 3, `LAYOUT_REFERENCE` 3, `TYPOGRAPHY_REFERENCE` 4, `COMPONENT_REFERENCE` 1, `IMPLEMENTATION_REFERENCE` 1, `COUNTER_REFERENCE` 1 |
| Coverage | **READY** |
| Diversity | **DIVERSE_ENOUGH** — "no informative axis is dominated by a single value" |
| Distinct values per axis | `industry` 5, `role` 6, `emphasis` 3, `light-dark` 2, `source-kind` 2, `surface` 1 |
| Provenance axes (reported, not voted) | `surface`, `source-kind` |
| Budget verdict | **WITHIN_BUDGET** |

The counter-reference is **Cohere**, retrieved by the counter search, recorded with
the anti-pattern it stands for:

> *a generic AI dashboard: a glassmorphic card grid with gradient glows, a centred
> hero and no information hierarchy*

## 8. Vertical slice

The exact request:

> *"Create a design direction for a serious desktop developer tool. It should feel
> precise, dense and calm, but not like a generic AI dashboard."*

Offline, deterministic, repeated runs producing identical evidence.

### References acquired

| Reference | Source kind | Evidence level | Patterns | Bytes |
|-----------|-------------|----------------|----------|-------|
| `DESIGN.md` (project) | `LOCAL_DESIGN_FILE` | `DIRECTLY_INSPECTED` | 6 | 1 007 |
| Cursor design system analysis | `CURATED_DESIGN_ANALYSIS` | `CURATED_ANALYSIS` | 17 | 21 771 |
| Warp design system analysis | `CURATED_DESIGN_ANALYSIS` | `CURATED_ANALYSIS` | 16 | 24 438 |
| Vercel design system analysis | `CURATED_DESIGN_ANALYSIS` | `CURATED_ANALYSIS` | 18 | 41 405 |
| Cohere design system analysis (counter) | `CURATED_DESIGN_ANALYSIS` | `CURATED_ANALYSIS` | 16 | 20 020 |

**73 observed patterns across 12 distinct dimensions.** Every curated reference is
recorded as a curated analysis; none is a first-party design system.

### Principles

**12 principles, all `SUPPORTED`** (each corroborated by ≥ 2 independent source
identities): `color-roles`, `component-geometry`, `density`, `depth`,
`information-hierarchy`, `layout-grid`, `navigation`, `radii`,
`responsive-behavior`, `spacing`, `surface-treatment`, `typography`.

### Treatments

```text
BORROW 17   ADAPT 52   AVOID 4   UNTREATED 0
```

`BORROW` the structural disciplines (hierarchy, grid, component geometry, density).
`ADAPT` the type and spacing scales. `AVOID` the counter-reference's surface
treatment. **Zero untreated patterns** — every extracted characteristic is accounted
for, which is the structural reason reference acquisition cannot decay into
reference cloning.

### The resulting direction

Status **`candidate`**, `approval_required: true`, gate **`G1D`**, no approval id.
**AR-220 approves nothing.**

| Section | Grounding |
|---------|-----------|
| `key_hierarchy` | REFERENCE_EVIDENCE |
| `visual_principles` | REFERENCE_EVIDENCE |
| `content_principles` | REFERENCE_EVIDENCE |
| `interaction_principles` | **PROJECT_CONSTRAINT_AND_REFERENCE** |
| `constraints` | REFERENCE_EVIDENCE |
| `reference_findings_adopted` | REFERENCE_EVIDENCE |
| `findings_rejected` | REFERENCE_EVIDENCE |

`ready_for_approval: true`, **ungrounded sections: none**, contract problems: none.

`interaction_principles` is `PROJECT_CONSTRAINT_AND_REFERENCE` because curated design
analyses document colour, type, spacing and components — they do not document how an
interface behaves over time. Those statements come from the project's own `DESIGN.md`
and are labelled `[project]`, attributed to the project, and never dressed as
something a reference said.

### Provenance: every major choice cites its evidence

| Why this… | Cited evidence |
|-----------|----------------|
| navigation density, information hierarchy, layout grid | Cursor, Warp, Vercel, Cohere (`CURATED_DESIGN_ANALYSIS` / `CURATED_ANALYSIS`) |
| typography, spacing, radii scales | all five, including the project's own `DESIGN.md` (`DIRECTLY_INSPECTED`) |
| panel/component behaviour | Cursor, Warp, Vercel, Cohere |
| the interaction rules | the project's own `DESIGN.md`, `[project]`-labelled |
| the colour palette | **the project's own tokens** — `LOCAL_DESIGN_FILE` / `DIRECTLY_INSPECTED`; the borrowed references supply roles, not values |

That last row is the answer to §32 of the brief, and it is checkable:
`reference_findings_adopted` never carries a project colour value, and the project's
`LOCAL_DESIGN_FILE` record is the only `DIRECTLY_INSPECTED` source for colour roles.

## 9. Reference economics

| Measure | Value |
|---------|-------|
| Project-local probes run | 4 (design documents, tokens, component library, Figma links) |
| Project identity established | `DESIGN_DOCUMENT`, `DESIGN_TOKENS`, `COMPONENT_LIBRARY` |
| CSS variables found | 12 |
| Component files found | 2 |
| External capability | `AVAILABLE`, mode `offline-fixture` |
| Candidates found | 12 primary + 12 counter-query |
| Deep inspections attempted | 8 |
| References retrieved | 4 external + 1 project-local |
| Bytes retrieved | **107 634** |
| Network requests during the slice | **0** |
| Bytes taken from the local frozen corpus | **107 634** of 107 634 (100 %) |
| Live requests ever made for this corpus | **4**, once, on 2026-10-03, by the recorder |
| Candidates skipped | 1 (`kraken` — no recording, no authorized fetch capability) |
| Budget verdict | `WITHIN_BUDGET` |
| Budget spent | `candidate_retrieval` 24/24, `deep_inspection` 4/8, `primary_references` 3/3, `counter_references` 1/2 |
| Recorded expansions | 2, both with reasons |
| Injection attempts found | 0 (none present in the recorded corpus) |
| Stopped because | "the reference budget was applied; Ariadne retrieved enough evidence to justify a direction and stopped rather than continuing to search" |

### Reading "0 network requests" without being misled

The vertical slice above performed **zero network requests**, and every one of its
107 634 retrieved bytes was read from disk. The 107 634 bytes were themselves
obtained from the network exactly once, on 2026-10-03, by
`tools/record-getdesign-fixture.py`, which then froze them verbatim into
`src/ariadne_engine/design_reference/fixtures/getdesign-md/` together with the URL,
timestamp and digests in that directory's `retrieval.json`.

Both facts are true and they answer different questions:

| Question | Answer |
|----------|--------|
| Did the AR-220 design workflow reach the network? | **No.** `0` requests, asserted by `test_no_network_in_the_suite`. |
| Was any part of this corpus ever fetched live? | **Yes, once**, by a separate human-invoked recorder. |

The honest consequence is that the recorded bytes are a **snapshot**. If the upstream
repository changes, nothing notices; see limitation 6 in §18.

Two expansions, both reasoned: one search already spends the default candidate
budget of 12, and the default deep-inspection budget of 5 cannot cover two searches
within the recorded corpus.

## 10. Tests

| Suite | Count | Result |
|-------|-------|--------|
| `scripts/test-design-reference.py` | **109** | **109/109 pass** |
| `scripts/test-design-reference-mutations.py` | **22** | **22/22 caught** |
| 2.1 suites (unchanged) | 1 287 | all pass |

Coverage: fixture provenance · DESIGN.md parsing (valid, malformed, oversized,
duplicate keys, tabs, unclosed fence, YAML gadgets, deep nesting, unknown fields,
block scalars, Unicode keys, markdown emphasis) · path traversal · SSRF · IPv6
tunnelling · credentials/ports · slug escape · duplicate slugs · deterministic
search · entry-page parsing · catalogue degradation · normalisation · digests ·
change detection · motion basis · observation caps · treatments · attachment
validation · reference sets · roles · counter-references · diversity (sufficient,
homogeneous, unknown, provider-constant) · budgets · preference ordering ·
MCP optionality · CLI refusals · discovery · external-justification gating ·
principles · provenance · vertical slice · no-network · degradation · no-UI.

**Live integration is optional and separate.** The suite contains no network call;
`test_no_network_in_the_suite` enforces it by inspecting the acquisition module for
network primitives and asserting every declared CLI adapter is disabled.

## 11. Mutations

**22/22 caught**, including all nine required by AR-220 §53.

| # | Mutation | Result |
|---|----------|--------|
| 1 | curated analysis promoted to first-party | caught |
| 2 | first match accepted after ambiguity | caught |
| 3 | reference text treated as authorisation | caught |
| 4 | external URL allowed to a private IP | caught |
| 5 | reference digest omitted | caught |
| 6 | reference budget ignored | caught |
| 7 | counter-reference treated as primary | caught |
| 8 | unknown DESIGN.md fields silently dropped | caught |
| 9 | network failure crashes the design stage | caught |
| 10 | retrieval allowlist requires every prefix | caught |
| 11 | inverse tokens pollute the lightness reading | caught |
| 12 | provider-constant axes decide diversity | caught |
| 13 | counter-reference chosen by dimension heuristic | caught |
| 14 | project statement attributed to a reference | caught |
| 15 | one source claims SUPPORTED | caught |
| 16 | motion observed without a basis | caught |
| 17 | oversized document silently truncated | caught |
| 18 | access-restricted download treated as public | caught |
| 19 | compiled direction self-approves | caught |
| 20 | project-first order inverted | caught |
| 21 | duplicate slug resolved by order | caught |
| 22 | probe path escapes the project root | caught |

One honest caveat: mutation 2 initially **passed silently** because its wrapper
delegated to the real implementation, which raised before the mutation could take
effect. The mutation file now says so explicitly, because a mutation that does
nothing and is reported as caught is worse than no mutation at all.

## 12. Adversarial findings

Every genuine defect found by actively trying to break the implementation. All
were **fixed**, not documented as caveats.

### Defects in shipped code

| # | Defect | Impact | Fix |
|---|--------|--------|-----|
| 1 | **Retrieval allowlist inverted** — raised unless *every* prefix matched | refused the provider's own documented host | require at least one match |
| 2 | **`sh -c` / `python -c` missing** from refused flags | the most common route from an argument to executed code | added `-c` |
| 3 | **Inverse tokens polluted the lightness read** | `inverse-canvas: #ffffff` made a near-black system report `light-dominant` | exclude `inverse*` tokens from the base surface |
| 4 | **Provider-constant axes decided diversity** | every single-provider set reported `TOO_HOMOGENEOUS` on an axis nobody chose | split voting vs provenance axes |
| 5 | **Counter-reference chosen by dimension heuristic** | picked a *positive* exemplar; the "do not become" clause described what it emulated | use the counter search's own result |
| 6 | **Offline prioritisation ran after truncation** | counter search retrieved nothing; direction built with no counter-reference | reorder before capping |
| 7 | **Transport errors propagated** | a third party's outage crashed the design stage | record and continue |
| 8 | **`digest_fields` is approval-subject-only** | rejected every design-reference payload | canonical-JSON digest |
| 9 | **Project `DESIGN.md` never parsed** | the *highest-priority* evidence yielded 0 patterns and 0 tokens | parse `DECLARED_LOCAL` documents |
| 10 | **Role budget lines never debited** | 4 primaries against a cap of 3 reported `WITHIN_BUDGET` | debit before validating |
| 11 | **Role caps did not shape selection** | the set accepted more primaries than the budget allows | cap during role assignment |

### Defects in my own work during this pass

| # | Defect | Impact |
|---|--------|--------|
| 12 | Block-scalar parser returned a tuple that was never unpacked | `description: \|` broke parsing; the loop re-read the scalar body as structure |
| 13 | `_principle_statement` used an obfuscated `[:0] or [...]` expression | worked by accident, unreadable |
| 14 | `_add_motion_observations` contained dead code against a nonexistent API | unreadable, untestable |
| 15 | YAML construct scan applied to the whole document | refused ordinary markdown emphasis (`**Linear**`) |
| 16 | Unsafe-construct patterns were ASCII-only | refused a published document over a Chinese field name |
| 17 | Candidate cap applied to the *index* instead of results | refused the real 73-row catalog to protect a smaller thing |
| 18 | `access_mode` field shadowed the `unavailable_reason()` method | capability record raised instead of reporting |
| 19 | Slice judged external research `YES`; acquisition re-judged `NO` | the caller's decision was silently overridden |
| 20 | BOM written as UTF-8 bytes rather than a code point | frontmatter silently unparsed — zero tokens with a valid digest |

Defects 12, 17, 18, 19 and 20 were all found by **running against real data or real
call paths**, not by reading the code. That is the single most useful observation in
this report: the live corpus and the live site found more than review would have.

## 13. MCP and CLI architecture

| Adapter | Declared | Enabled | Verdict |
|---------|----------|---------|---------|
| `figma-mcp` | 4 verbs | no | unavailable, with reason |
| `github-mcp` | 4 verbs | no | unavailable, with reason |
| `internal-design-system-mcp` | 4 verbs | no | unavailable, with reason |
| `getdesign-cli` | probe/search/inspect/fetch | no | Node package that writes into a project; Ariadne never installs it |
| `designmd-cli` | probe/search/inspect/fetch | no | optional; not required |
| `shadcn-registry-cli` | probe/search/inspect/fetch | no | optional in both directions |
| `getdesign-md` | discover/retrieve/inspect | **yes** | offline fixture corpus |

`required_for_core: false` for every one. No MCP client, no subprocess import, no
Node dependency. Deferred: real MCP transports, a registry client, caching of
transport responses.

## 14. Security

18 attack categories tested; all refused or neutralised. Covered in
[06-REFERENCE-SECURITY.md](06-REFERENCE-SECURITY.md).

**One documented limitation:** a hostname that *resolves* to a private address
(`10.0.0.1.nip.io`) is **not** refused by `require_fetchable_url`, and the suite
asserts that it passes. The check resolves nothing, which is what makes it
deterministic and offline-testable. The gap is closed structurally: every adapter
targets a fixed host set from module constants, live retrieval requires an
operator-supplied allowlist, and `raw_url()` cannot be pointed elsewhere by any
catalog input.

## 15. Boreal

**BOREAL MUST REMAIN UNTOUCHED — confirmed.**

`git status` in this worktree contains no Boreal path. No Boreal file was read,
written, moved or referenced. Every changed file is under
`src/ariadne_engine/`, `scripts/`, `docs/v2/2.2/`, `CHANGELOG.md`,
`THIRD_PARTY_NOTICES.md` and the AR-220 branch itself.

## 16. Files changed

### Added

```text
src/ariadne_engine/design_reference/__init__.py
src/ariadne_engine/design_reference/safety.py
src/ariadne_engine/design_reference/designmd.py
src/ariadne_engine/design_reference/normalize.py
src/ariadne_engine/design_reference/getdesign.py
src/ariadne_engine/design_reference/discovery.py
src/ariadne_engine/design_reference/sets.py
src/ariadne_engine/design_reference/transports.py
src/ariadne_engine/design_reference/direction.py
src/ariadne_engine/design_reference/acquire.py
src/ariadne_engine/design_reference/vertical_slice.py
src/ariadne_engine/design_reference/fixtures/getdesign-md/{catalog,retrieval}.json
src/ariadne_engine/design_reference/fixtures/getdesign-md/{linear.app,cursor,warp,vercel,cohere}.md
scripts/test-design-reference.py
scripts/test-design-reference-mutations.py
tools/record-getdesign-fixture.py
docs/v2/2.2/01..08
```

### Modified

| File | Change |
|------|--------|
| `src/ariadne_engine/contracts.py` | AR-220 vocabulary, `design_reference_sets` collection, `reference_set_problems`, `reference_set_member_problems`, `design_reference_classification_problems` wired into `reference_problems` |
| `src/ariadne_engine/__init__.py` | export `design_reference` |
| `scripts/ariadne.py` | `design-references` and `design-reference-capability` verbs |
| `scripts/check.py` | `VENDORED_FIXTURES` exemption for the frozen corpus |
| `CHANGELOG.md` | AR-220 entry |
| `THIRD_PARTY_NOTICES.md` | AR-220 position: no code, MIT data, no affiliation |

**Not modified:** `VERSION`, `pyproject.toml`, `LICENSE`, `RELEASE-NOTES.md`,
`README.md`, every `v2.1.0` and `v2.1.0rc1` tag, and every Boreal file.

## 17. Why `VERSION` was not bumped

Tried `2.2.0a1`; it fails `test-release.py` — `repository version surfaces agree`
requires the release-notes heading **and** install URLs to name the new version,
which means writing install instructions for `ariadne-2.2.0a1-py3-none-any.whl`, a
release that must not exist. Reverted to `2.1.0` and recorded development status in
`CHANGELOG.md`.

The version becomes `2.2.0a1` when a release candidate is actually cut. AR-220
claims no release, no tag and no GitHub release.

## 18. Limitations, honestly

**Substantive:**

1. **Diversity is coarse.** It measures recorded classification, not aesthetic
   similarity. Four dark developer-tool analyses plus one project document read as
   `DIVERSE_ENOUGH`, and a person would call that narrow. The check catches the
   obvious case; it does not solve the problem.
2. **Search is lexical.** No embeddings, by choice — an unauditable relevance model
   is worse. A relevant entry sharing no vocabulary with the query is missed.
3. **The frozen corpus is 5 documents out of 550+.** Offline acquisition searched the
   full 73-row index and skipped a higher-ranking candidate (`kraken`) because it
   has no recording. Breadth is a fixture-size limitation, not an architecture one.
4. **MCP and CLI are boundaries, not integrations.** No client, no transport, no
   subprocess. A real integration means implementing an adapter, nothing more.
5. **`preview.html` is public but unparsed.** A visible, unauthenticated source of
   rendered design evidence that this phase deliberately did not consume.
6. **No automatic cache refresh or drift monitoring.** Fixtures are refreshed by
   hand. Change *detection* exists; continuous monitoring does not.
7. **Motion is never observed in this corpus.** None of the five documents declares
   a motion basis, so no motion observation was produced — the honest outcome of a
   gate that refuses to infer motion from static tokens.
8. **The counter-reference is chosen by query, not by reasoning.** It is the
   reference the counter search retrieved, which is defensible but not the same as
   demonstrating it *is* the anti-pattern.

**Environmental:**

9. getdesign.md markup coupling is real; degradation to fewer fields is the designed
   failure mode, not a crash, but it is not verified against a redesign.
10. The live retrieval happened once. No scheduled re-verification exists.

## 19. Next phase boundary

AR-220 stops at approved-ready direction evidence. No UI implementation, no
rendered capture, no reference-aware critique, no bounded refinement.

```
AR-221  Grounded Design Execution & Reference-Aware Critique
        approved design direction → implementation → rendered capture
        → reference-aware critique → bounded refinement
```

Not started.

## 20. Exit criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | 2.1 baseline green | ✅ 12/12, all suites pass |
| 2 | `DesignReference` as provider-neutral evidence | ✅ extends the AR-202D record family |
| 3 | `ReferenceSet` exists | ✅ validated, cross-checked |
| 4 | source/evidence kinds explicit | ✅ 10 kinds, 6 levels |
| 5 | getdesign.md has a real adapter | ✅ search/fetch/normalize |
| 6 | one live public reference retrieved and normalized | ✅ 5 documents, provenance recorded |
| 7 | regression tests use frozen fixtures, no live network | ✅ enforced by a test |
| 8 | curated ≠ first-party | ✅ constant + validator + mutation |
| 9 | local `DESIGN.md` parsing works | ✅ 6 patterns, 5 token groups on the project fixture |
| 10 | reference text cannot grant authority | ✅ 6 injection classes + mutation |
| 11 | SSRF / traversal boundaries hold | ✅ 18 categories, 1 documented limitation |
| 12 | reference budgets enforced | ✅ 4 lines, refuse-before-increment, role caps shape selection |
| 13 | MCP boundary without mandatory MCP | ✅ 3 declared, all disabled |
| 14 | CLI boundary without mandatory Node | ✅ 3 declared, all disabled, no subprocess |
| 15 | Design Intelligence consumes a `ReferenceSet` | ✅ compiler + provenance |
| 16 | end-to-end vertical slice completes | ✅ offline, deterministic |
| 17 | every major direction choice cites evidence | ✅ 7/7 sections grounded, 0 ungrounded |
| 18 | no UI implementation | ✅ asserted by test |
| 19 | no Boreal file touched | ✅ confirmed |
| 20 | all old regression/release gates green | ✅ 1 287 2.1 tests + 12/12 gate |

**All 20 criteria met.**

## 21. Closure status

```text
AR-220 COMPLETE WITH KNOWN LIMITATIONS
```

The limitations in §18 are real and are stated rather than smoothed over. The
foundation is sound: the evidence substrate is independently verifiable, every
major design choice cites its support, and the adversarial pass found and fixed 20
genuine defects — 11 of them in shipped code.