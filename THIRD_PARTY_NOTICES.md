# Third-party notices - Ariadne 2.1 (AR-206)

## Scope

This file records the third-party position of the **Ariadne 2.1 native Decision
Runtime** (feature AR-206, branch `v2/2.1-native-decision-runtime`). It covers
`src/ariadne_engine/decisions/runtime/` and everything AR-206 added to the engine
contract, the integrations, the CLI and the test suites.

## The position, stated plainly

**AR-206 added no third-party runtime component and no third-party code.**

The reference bounded engine, its sidecar process, its transport, its weight
builder and its seed weights are original Ariadne code. The reference engine is
pure Python standard library. It ships no model file, downloads nothing, contacts
no network, and declares no dependency.

This is not an aspiration the packaging happens to satisfy; it is asserted by the
release tooling and the functional suite:

- `pyproject.toml` declares `dependencies = []` and `requires-python = ">=3.10"`,
  with an in-tree build backend (`ariadne_backend`) and no build requirements.
- A walk of the import graph across `src/ariadne/`, `src/ariadne_engine/`,
  `scripts/` and `build_backend/` resolves to the standard library only. (The one
  first-party package name outside `src/`, `arbench`, is Ariadne's own benchmark
  package under `benchmarks/`.)
- `scripts/test-decision-runtime.py` reads `pyproject.toml` and fails if any of
  `torch`, `transformers`, `safetensors`, `huggingface`, `onnxruntime`, `numpy`,
  `scikit-learn` or `scipy` appears.
- The same suite asserts the runtime package contains no trainer, and that the
  only module writing a weight file is the explicit seed builder.
- `docs/v2/AR-205/03-DISTRIBUTION.md` records the same zero-third-party-import
  result for released 2.0.

## The standard library modules used

AR-206 code imports only these, all from the Python standard library:

```
__future__    argparse      dataclasses    hashlib       json
math          ntpath        os            pathlib       platform
re            signal        subprocess     sys           threading
time          typing
```

By module, for the record:

| Module | Standard-library imports |
|---|---|
| `__init__.py` | `__future__` |
| `evaluation.py` | `__future__`, `hashlib`, `json`, `time`, `typing` |
| `export.py` | `__future__`, `hashlib`, `json`, `pathlib`, `typing` |
| `integrity.py` | `__future__`, `os`, `pathlib`, `platform`, `typing` |
| `manifest.py` | `__future__`, `hashlib`, `json`, `ntpath`, `pathlib`, `typing` |
| `observe.py` | `__future__`, `typing` |
| `profiles.py` | `__future__`, `dataclasses`, `hashlib`, `json`, `typing` |
| `promotion.py` | `__future__`, `typing` |
| `provider.py` | `__future__`, `typing` |
| `reference.py` | `__future__`, `dataclasses`, `hashlib`, `json`, `math`, `pathlib`, `re`, `typing` |
| `schema.py` | `__future__`, `dataclasses`, `hashlib`, `json`, `typing` |
| `seeds.py` | `__future__`, `pathlib`, `typing` |
| `selection.py` | `__future__`, `typing` |
| `session.py` | `__future__`, `os`, `pathlib`, `platform`, `typing` |
| `shadow.py` | `__future__`, `typing` |
| `shortlist.py` | `__future__`, `hashlib`, `json`, `re`, `typing` |
| `sidecar.py` | `__future__`, `argparse`, `json`, `pathlib`, `sys`, `typing` |
| `transport.py` | `__future__`, `json`, `os`, `pathlib`, `signal`, `subprocess`, `sys`, `threading`, `typing` |

`sidecar.py` also has a fallback absolute import of `ariadne_engine`, which is
Ariadne's own package, used only when the sidecar is launched by file path without
package context.

## The weights

The shipped weight file is **data, not code**, and its provenance is Ariadne's own.
`ariadne_engine.decisions.runtime.seeds.SEED_SOURCE` reads, verbatim:

> ariadne deterministic decision tables (ar-205d decision-intelligence
> answer-space vocabularies and projection contracts); rule-derived features, not
> a trained corpus

The families are fitted from rule-derived examples written against the projection
field names Ariadne's own `decisions.projections` module declares, over the
answer spaces Ariadne's own contracts already publish
(`DECISION_CLASSIFIABLE_FAILURE_CLASSES`, `REVIEW_ESCALATIONS`,
`EVIDENCE_RELEVANCE_ANSWERS`, `ROUTE_FAMILIES`). The installation is two JSON
files of roughly 97 KB in total.

**They are not trained parameters and they are not presented as such.** They are
feature encodings of rules the engine already knew. The weight file records its
source, the install output says "probabilities from this engine are uncalibrated
by construction", and every answer is labelled `PROVIDER_PROBABILITY`. A
consumer of this file should hold it to that description and no stronger one.

## The pre-existing 2.0 situation

Stated only as far as it is verifiable from this repository, and not overstated:

- **`pyproject.toml` has declared `dependencies = []` since 2.0.** There is no
  third-party dependency to attribute, before or after AR-206.
- **`src/` contains no third-party imports**, confirmed by AST scan above. The
  claim recorded in `docs/v2/AR-205/03-DISTRIBUTION.md` and
  `docs/v2/AR-205/12-AR-205-REPORT.md` - zero third-party imports in shipped code,
  no bundled third-party code - still holds after 2.1.
- **The launcher is first-party.** `src/ariadne/` is Ariadne's own installation,
  update, rollback and uninstall controller. It imports only the standard library.
- **`adapters/` is configuration, not code.** It is a set of markdown contract
  documents (`codex.md`, `claude-code.md`, `claude-reasoner.md`, `cursor.md`,
  `reasoner-contract.md`, `codex-baseline.md`, `SKILL.md`) and one JSON
  capability catalogue (`reasoners.json`). These describe how to drive *external*
  reasoning tools (the `codex` and `claude` executables). No third-party source is
  bundled, and nothing in them is a copy of a vendor's code - they are Ariadne's
  own interface contract.
- **The `JevShapedAdapter` is Ariadne's own interface, not a Jev client.**
  `src/ariadne_engine/decisions/providers.py` defines a vendor-shaped capability
  mapping (`JEV_SHAPED_CAPABILITIES`) and an injection-only adapter class. It
  performs no network call, requires no credential, is activated only when an
  operator supplies an interface object, and its live use is recorded as
  `NOT_EXECUTED`. It is released 2.0 surface, not part of AR-206, and no code from
  any Jev implementation is present in this repository. See
  `docs/v2/AR-205D/07-PROVIDERS.md`.
- **Optional external tools are not dependencies.** Where Ariadne can drive an
  external executable (a reasoning CLI), the executable is the user's to install
  and the feature is opt-in. Absence is recorded as capability state, never as a
  crash.

## No NOTICE file

Ariadne ships `LICENSE` (Apache License 2.0) and does not ship a `NOTICE` file.
Apache 2.0 section 4(d) requires a `NOTICE` file to be handled only when the work
includes one; because no third-party attribution notices exist for AR-206, none
is created here. This file is a provenance statement, not an Apache `NOTICE`
file, and carries no attribution obligations.

## If that ever stops being true

The honest failure modes are worth naming in advance:

1. a checkpoint-backed engine installed as a Decision Runtime, bringing its own
   licence and its own notices;
2. an operator-supplied embedding function passed to the `embedding` shortlist
   strategy;
3. a `JevShapedAdapter` activated against a live third-party service.

None of these is shipped by AR-206, and each is an explicitly external,
operator-supplied component. If one enters a distribution, it must be recorded
here with its licence, its notices and its attribution obligations before that
distribution ships. A dependency added silently inside `pip install ariadne` is
precisely the failure this architecture refuses.

See also `LAYA-ADAPTATION.md`, which records the adaptation question for this
feature specifically.

---

# Third-party notices - Ariadne 2.2 development (AR-220)

## Scope

This section records the third-party position of **AR-220 Grounded Design
Intelligence** (branch `v2/2.2-grounded-design-intelligence`, no release). It adds
`src/ariadne_engine/design_reference/`, the AR-220 vocabulary in
`src/ariadne_engine/contracts.py`, two CLI verbs, two test suites and one fixture
recorder.

## Code position

**AR-220 added no third-party runtime component and no third-party code.**

Every line of `design_reference/` is original Ariadne code. It is pure Python
standard library, consistent with the AR-206 position above:

- the DESIGN.md parser is a bounded YAML-subset parser written for this feature,
  not a wrapper around PyYAML or any other library;
- `pyproject.toml` is unchanged and still declares `dependencies = []`;
- no MCP server, Node package or CLI tool is installed, imported or required;
- the getdesign.md, MCP and CLI adapters are *boundaries*: they declare what a
  source may provide and refuse anything undeclared. None of them ships a client.

The same assertion is enforced by the AR-220 suite: `test_no_network_in_the_suite`
inspects the acquisition module for network primitives and asserts every declared
CLI adapter is disabled.

## Data position: the frozen getdesign.md corpus

This is the part of AR-220 that touches other people's material, so it is recorded
in detail.

`src/ariadne_engine/design_reference/fixtures/getdesign-md/` contains five
`DESIGN.md` documents retrieved once from the **public, MIT-licensed repository
`VoltAgent/awesome-design-md`** (repository: <https://github.com/VoltAgent/awesome-design-md>,
licence: MIT), together with the catalog index parsed from that repository's README
and the provenance of every retrieval in `retrieval.json`.

| Item | Detail |
|------|--------|
| Source repository | `VoltAgent/awesome-design-md` |
| Licence | MIT |
| Retrieved documents | `linear.app`, `cursor`, `warp`, `vercel`, `cohere` |
| Retrieved bytes | 24 354 / 21 771 / 24 438 / 41 405 / 20 020 |
| Retrieved at | 2026-10-03T19:18Z (one retrieval; frozen) |
| Modification | **None.** The bytes are stored verbatim so the recorded digest describes what the source returned. |

### Why the repository and not the catalog

getdesign.md's Terms of Service (section 7) prohibit "automated means to scrape
the Service". The raw `DESIGN.md` files are separately published by the
maintainers in an open MIT-licensed repository, which is both a permitted path and
the one the site itself documents for agents (`npx getdesign@latest add {slug}`).
Ariadne therefore reads the repository, performs **no crawling**, follows no links,
walks no sitemap and requests no gated endpoint.

### Attribution and the identity boundary

Every reference produced from this corpus records
`source_provider = getdesign.md`, `source_kind = CURATED_DESIGN_ANALYSIS` and
`attribution = "getdesign.md curated analysis via VoltAgent/awesome-design-md (MIT)"`.

Each entry page states: *"Independent analysis of publicly observable patterns,
curated as a starting point for inspiration. Not affiliated with or endorsed by"* the
referenced brand, and the Terms repeat that these documents *"are not official design
systems from the listed companies."* Ariadne records that classification as a
constant in the adapter: there is no code path that can reclassify a curated
analysis as `FIRST_PARTY_DESIGN_MD`.

Trademarks, wordmarks, logos and imagery referenced by these documents remain the
property of their respective owners and are used nominatively. Ariadne stores no
logo, wordmark or image from any of them.

## The separate `getdesign` project

`MohtashamMurshid/getdesign` (MIT, <https://github.com/MohtashamMurshid/getdesign>)
is a **different project** from getdesign.md. It is on-demand design-system
extraction from any URL, with an implemented web app and agent skill and a planned
HTTP API, CLI and TypeScript SDK.

AR-220 studied its documented 9-section extraction contract and its grounding
principles. **No code was copied or adapted from it.** Ariadne's controlled pattern
vocabulary was written for this feature against the public `DESIGN.md` corpus, and
Ariadne's parser targets the Google Stitch `DESIGN.md` frontmatter shape rather than
that project's output. Ariadne is not affiliated with, endorsed by or powered by
either project. Full audit: `docs/v2/2.2/03-GETDESIGN-MD-AUDIT.md`.

## Google Stitch DESIGN.md specification

`DESIGN.md` is a third-party interchange format introduced by Google Stitch. Ariadne
consumes it through an adapter and never adopts it as an internal canonical schema;
unknown fields are preserved and warned about rather than discarded. See
`docs/v2/2.2/04-DESIGN-MD-FORMAT.md`.
