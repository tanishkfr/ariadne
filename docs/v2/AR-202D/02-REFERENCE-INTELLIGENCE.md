# AR-202D — Reference intelligence

Source: `src/ariadne_engine/references.py`. Contract: `contracts.reference_problems`,
`contracts.reference_analysis_problems`.

## 1. The lifecycle

```
FOUND ──→ ACCESSIBLE ──→ INSPECTED ──→ ANALYSED ──→ USED
  │            │              ↑            │
  └────────────┴──→ INACCESSIBLE (terminal, blocker required)
```

| State | What it means | What it requires |
|---|---|---|
| `FOUND` | the source exists and is locatable | a source, a locator, an adapter name |
| `ACCESSIBLE` | the bytes or interface were reachable | the retrieved content digest |
| `INSPECTED` | somebody looked, with evidence | a hashed artifact + ≥1 concrete observation |
| `ANALYSED` | observations were generalised | citations to inspections that exist |
| `USED` | a design decision cites it | a decision, a principle, an artifact anchor |
| `INACCESSIBLE` | it could not be reached | a blocker; no inspection, analysis or usage |

Rules enforced in code:

* **No state is skipped.** `analyse` on a `FOUND` record is refused with "a
  reference must be INSPECTED before it can be ANALYSED".
* **`INACCESSIBLE` is terminal and honest.** It is reachable only before anything
  was observed; once a real inspection exists, "unreachable" is no longer the
  truth about the source, so the transition is refused. An inaccessible record
  cannot carry inspection evidence, analysis or usage — the contract validator
  rejects it.
* **A URL is not an inspection.** Registration records only that a locator exists;
  the title is also refused if it asserts a claim ("best practice: …"), because a
  title is not provenance.
* **Re-inspection and re-analysis are allowed, duplicates are not.** A reference
  visually inspected can later be interaction-inspected (`INSPECTED → INSPECTED`),
  and the same evidence re-recorded identically is refused as adding nothing.
* **Artifacts are re-hashable.** Evidence must be a real, non-empty file inside the
  project; the record keeps its digest, and `design.stale_requirements` /
  `render.stale_records` re-hash it before any closure or critique trusts it.
* **Containment is checked before anything is stored.** Inspection, usage and
  source-claim artifacts are resolved (`..`, separators, drive letters and
  symlinks included) and must land inside the project, so a citation cannot pull
  an unrelated file into provenance. The path helpers are
  `contracts.resolved_within` / `contracts.contained_evidence_path`.
* **A refusal writes nothing.** Each lifecycle move validates the intended record
  before applying it (`references._transition` with `updates`), so a refused call
  leaves the record byte-identical rather than half-mutated.
* **A local reference that cannot be read is `INACCESSIBLE`.** `mark_accessible`
  re-reads and hashes a local locator and refuses when the file is missing; only a
  genuinely remote source may record an adapter-declared digest
  (`content.digest_source` is `local-verified` or `declared`).

## 2. Inspection types and claim bounds

Three inspection types, deliberately not interchangeable:

| Inspection | Evidence it needs | Claim kinds it can support |
|---|---|---|
| `CONTENT` | the retrieved text/markup/registry entry | `structure`, `content` |
| `VISUAL` | a rendered appearance (screenshot, design file) | `appearance`, `structure`, `content` |
| `INTERACTION` | a transcript of behaviour over time | `behaviour`, `timing`, `feedback`, `appearance` |

`INTERACTION` includes `appearance` because watching a live interface necessarily
includes seeing it; nothing else is transitive. A claim whose kind exceeds the
recorded inspection is refused (`references.INSPECTION_SUPPORTS`), and the same
bound is re-checked when a reference is marked used.

This is the rule the AR-200 design philosophy needed and never had: a worker can
no longer upgrade "I read the HTML" into "the interaction feels good"
by asserting it. The lifecycle recording is what makes the assertion checkable.

**A valid partial record is valid.** A reference may be `VISUALLY_INSPECTED` and
`ANALYSED` without ever being interaction-inspected. AR-202D does not mark such a
record incomplete: interaction inspection is recorded as an *opportunity* in the
evidence route (`routing.DESIGN_OPTIONAL_EVIDENCE_NEEDS`) and never blocks.

## 3. Adapters

An adapter declares what it can do and answers only for those capabilities;
`ReferenceAdapter.require` refuses anything else, so a caller cannot obtain
evidence from an adapter that never claimed to produce it.

| Capability | Meaning |
|---|---|
| `discover` | return candidate locators for a query |
| `retrieve_metadata` | title, media type, size, content digest |
| `retrieve_content` | the retrieved digest and a short excerpt |
| `inspect_visual` | materialise a visual artifact for visual inspection |
| `inspect_interaction` | materialise an interaction transcript |

Shipped adapters:

| Adapter | Source type | Capabilities | Availability |
|---|---|---|---|
| `local-reference` | `local-file`, `project-screenshot` | discover, metadata, content, visual | always (project `design/references/**`) |
| `project-document` | `project-document` | discover, metadata, content | always (project documents) |
| `approved-url` | `approved-url` | discover, metadata, content, visual | **only** with an operator-configured HTTPS allowlist and an authorized fetcher |
| `paid-design-library` | `paid-provider` | discover, metadata, content, visual | **only** with a licensed interface and a licence reference |
| `fixture-reference` | `fixture` | declared by the fixture | offline, deterministic, tests only |
| `UnavailableAdapter` | — | declared, disabled | reports why it cannot act |

Non-negotiable properties, all tested:

* read-only — no adapter writes to the project, installs anything, or posts anything;
* no scraping, no authentication bypass, no gated-content access;
* a disabled adapter is a *valid* adapter: it reports its own reason and every
  retrieval becomes a recorded `INACCESSIBLE` with that blocker;
* no fabricated evidence from an unavailable source (there is no code path that
  could produce one);
* capabilities are never inferred from a model or vendor name.

### Optional provider (Mobbin-class)

`OptionalProviderAdapter` is not required, not bundled, and not paid for by
Ariadne. Without an authorized licensed interface it returns an inaccessible
result with a blocker, and Ariadne provides the whole design workflow without it.
There is no web-scraping path in the class and nowhere to add one without adding
a licensed interface object explicitly.

### Approved public web references

`ApprovedUrlAdapter` implements the contract and the refusal. Live fetching
happens only when the runtime is explicitly given an authorized fetch capability,
and even then the discipline is fixed in the adapter: HTTPS only, explicit
allowlist, no credentials, no project content in the request, byte caps, and
robots/access restrictions honoured. With no capability configured, the honest
answer is "unavailable".

The decision to make this contract-only in AR-202D is recorded in `10-ADR.md`
(ADR-006): a design milestone must not introduce a network surface, and every
claim AR-202D makes is verifiable offline.

## 4. Discovery and provenance of a search result

Where discovery is used, the record keeps the query, the returned candidates, the
one that was selected, and the accessibility outcome. Only the *selected*
candidate becomes a reference record, and it still starts at `FOUND`. A search
result snippet is never recorded as inspection and never becomes analysis:
`references.register` has no observation field, by construction.

## 5. Analysis

An analysis record separates four things that are usually conflated:

| Field | Question it answers |
|---|---|
| `observation` | what was actually observed |
| `interpretation` | what the engine/worker believes it means |
| `applicability` | whether the pattern is appropriate *for this project* |
| `decision` (`adopted` / `rejected` / `deferred`) | what may influence the current design |

Each finding names a dimension (`hierarchy`, `composition`, `navigation`,
`typography`, `spacing`, `interaction`, `motion`, `information-density`,
`responsiveness`, `accessibility`, `component-patterns`, `content-structure`,
`trust-signals`, `conversion-structure`), cites the inspection ids it derives
from, and records an adoption decision (`adopted` / `rejected` / `deferred`).

**An adopted finding must name a mechanism.** "Two sites do it" is not a
mechanism, and `mechanism` is required exactly when `decision == "adopted"`. This
is the executable form of "do not call something a best practice merely because
two websites do it".

## 6. Diversity

`references.diversity_notes` reports deterministic facts over the analysed set:
how many distinct sources were analysed, which dimensions were covered, and which
adopted mechanisms *converge* across sources. It deliberately makes no judgement:
the returned `convergence_note` states that convergence records that independent
sources used the same mechanism, not that the mechanism is correct for this
project. There is no enforced reference count — quality over quantity — and
meaningful disagreement is preserved because every rejection is recorded.

## 7. Failure kinds

| Kind | Class | Raised when |
|---|---|---|
| `REFERENCE_UNAVAILABLE` | `CONTEXT_FAILURE` | a required reference cannot be reached |
| `REFERENCE_INSPECTION_FAILED` | `VALIDATION_FAILURE` | inspection cannot produce usable evidence |
| `REFERENCE_PROVENANCE_INVALID` | `VALIDATION_FAILURE` | a record claims a state its evidence cannot support |

All three map onto classes whose retry and escalation flags already exist in
`execution.FAILURE_FLAGS`; AR-202D records the design kind beside the class so an
operator can see which reference condition happened, and adds no duplicate
taxonomy.
