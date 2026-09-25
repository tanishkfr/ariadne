# AR-200 / 05 — DESIGN INTELLIGENCE SUBSYSTEM

Design intelligence is a core v2 pillar, not a prompt collection. This document specifies the subsystem; AR-200 implements none of it (see 08-ROADMAP → AR-202D).

## 0. What already exists (do not rebuild)

| Layer | Existing implementation | Verdict |
|---|---|---|
| Skill selection from a project assessment | `creative-intelligence.py:177-267` (10-dimension assessment), `354-490` (depth + selection rules) | KEEP |
| Capability ladder + G2 block | `capability_plan` `creative-intelligence.py:312-351`; `references/capabilities.json`; `install_authority` asserted by `check.py:169-207` | KEEP, HARDEN freshness + verification |
| Reference provenance | `found` / `inspected` / `inaccessible`, evidence hashing, ≤2 mechanisms, borrow/reject, `used_by` back-references (`creative-intelligence.py:52`, `602-651`, `943-958`, `1033-1069`) | KEEP, EXTEND to 5 states |
| Design direction checks | thesis non-generic (regex-banned words), tension, signature + mobile equivalent, ≥3 rejections, 10-row G1 check (`creative-intelligence.py:1073-1112`) | KEEP |
| Implementation targets derived from the locked direction | `creative-operations.py:236-314` (`derive_requirements`), `317-334` (QA plan) | KEEP |
| Visual-evidence ladder | `code-suggests` → `rendered` → `observed` → `verified` with `verified` requiring prior rendered/observed evidence (`creative-operations.py:408-451`) | KEEP as schema, REDESIGN enforcement (instruments) |
| Internal creative review | 10 dimensions, evidence IDs, parent chain, 2-iteration budget (`creative-operations.py:484-528`, `1178-1193`) | KEEP |
| Social intelligence | contract v3, freshness ≤180 d, user-only metrics, 3-result rule (`creative-operations.py:595-1009`) | KEEP (out of v2 core scope; not broken) |
| Rendered capture/inspection | **MISSING everywhere** | ADD (opt-in instrument) |
| Reference retrieval | **MISSING in Ariadne**; Boreal has an HTTPS/robots/consent adapter | EXTRACT (opt-in) |

## 1. Reference adapters

Adapters are read-only sources of design evidence. Each returns a `ReferenceCandidate`; none may install anything, post anything, or touch the project.

| Adapter | Source | Default | Evidence it can produce |
|---|---|---|---|
| `local-reference` | Files/images/PDFs the operator places in the project (`design/references/**`) or points at | enabled | digest + MIME + dimensions/duration; visual inspection only |
| `project-document` | The project's own docs (`PROJECT.md`, `DESIGN.md`, `RESEARCH.md`, previously recorded ledger entries) | enabled | digest + quoted anchor (already implemented as artifact anchors) |
| `approved-url` | An operator-approved HTTPS URL list, fetched with the extracted Boreal discipline: HTTPS only, `robots.txt` honoured, byte cap, content-type allowlist, no credentials, **no project content in the request** | disabled | digest-verified excerpt + HTTP status + fetch timestamp |
| `official-api` | Documented public APIs with explicit terms (e.g. a component registry API) | disabled | structured record + provider + retrieved_at |
| `mcp-provider` | An MCP server the operator configures | disabled | tool output + server identity + invocation record |
| `paid-library` (e.g. Mobbin-class) | Operator's own paid account, accessed only through its licensed interface | disabled, never bundled | provider record + licence reference + retrieval method |

Rules (enforced in code, not prose):
1. No scraping of gated or login-protected resources. An adapter that cannot establish a licensed interface returns `inaccessible` with a blocker — which is a *valid, recorded* outcome, not a failure.
2. A reference that could not be fetched is never described from memory. The existing ledger already enforces this for `inaccessible` ("carries invented observations" → problem, `creative-intelligence.py:957-958`).
3. Every adapter call records: adapter id, request digest, response digest, timestamp, licence note. `request_contains_project_content` must be `false` (adopted from Boreal's record shape).
4. Adapters are disabled by default; enabling one is an operator action recorded in the ledger.

## 2. Reference provenance

Extend the current three states to five, preserving every existing guard:

```
FOUND ──→ ACCESSIBLE ──→ INSPECTED ──→ ANALYSED ──→ USED
   └──────────────────────→ INACCESSIBLE (blocker required; terminal)
```

| State | Meaning | Required evidence (validated in code) | Forbidden |
|---|---|---|---|
| `FOUND` | The reference exists and is locatable (search result, operator mention, registry entry) | locator + how it was found + adapter id | any claim about its content |
| `ACCESSIBLE` | The bytes/interface are actually reachable | retrieval record: status, digest, size, MIME, timestamp, licence note (for URLs/APIs) | any observation yet |
| `INSPECTED` | A human or agent actually looked at it | inspection record with `kind ∈ {visual, interaction, code, content}`, viewport(s) where applicable, ≥1 concrete observation, ≤2 mechanisms, evidence artifact with digest | claims beyond what was inspected; interaction claims require `kind=interaction` evidence (a screenshot alone cannot support a behaviour claim) |
| `ANALYSED` | Observations were generalised into design implications | analysis record: implication, design_fit, constraints, and the observation IDs it derives from | analysis with no INSPECTED parent |
| `USED` | A concrete design decision cites it | decision record: decision, principle, requirement id, artifact anchor, and the analysed reference id | `USED` without an `ANALYSED` parent; reference-backed decisions without ≥1 inspected reference (already enforced: `creative-intelligence.py:753-758`) |

**Visual vs interaction inspection is a first-class distinction** (it is the weakest part of the current model): `kind=visual` may support composition, colour, typography and layout claims; `kind=interaction` may support motion, feedback, timing and state claims. A claim whose kind exceeds its evidence is rejected with a typed problem, exactly like the existing "inaccessible carries invented observations" guard.

Mapping to the current schema: `found` → `FOUND`; `inspected` → `INSPECTED` (with `inspection.kind` already present as `content|visual|interaction`); `inaccessible` → `INACCESSIBLE`. `ACCESSIBLE` and `ANALYSED` are new and are the states that make retrieval and generalisation auditable. Ledger schema version is already 2 with a `SUPPORTED_SCHEMA_VERSIONS` tuple (`creative-intelligence.py:26-27`), so the extension is a versioned, non-destructive addition.

## 3. Component intelligence

Problem: the current registry answers "which libraries exist" but not "is this the *smallest* solution, and is it safe to adopt here". Keep the existing minimum-solution ladder and make each rung produce a recorded decision:

```
1 existing project component      → use it (record the component + version + digest)
2 native platform capability      → use it (record the platform + support status)
3 project-local implementation    → prefer for small needs (record LOC + maintenance owner)
4 already-approved dependency     → reuse (record the approval id; no new G2)
5 registered candidate            → require an up-to-date registry entry + evaluation record
6 bounded external research       → registry is stale or the need is new; produce an evaluation record
   (never an install; installation is G2 and human-only)
```

Evaluation record (required before a candidate may be selected) — extends the current registry fields:

```
candidate_id, capability, need_id,
compatibility   {framework, version_range, peer_deps, status: verified|claimed|unknown, evidence}
accessibility   {wcag_level, keyboard, screen_reader_notes, evidence}
licence         {spdx, url, commercial_ok: bool, obligations, checked_on}
dependencies    {direct, transitive_count, weight, supply_chain_flags}
maintenance     {last_release, release_cadence, maintainers, open_security_advisories, checked_on}
design_fit      {why_this, why_not_alternatives[≥1], constraints}
verification    {ran_locally: bool, method, artifact_digest}
```
Rules: no automatic installation (unchanged G2 authority); an `unknown` field is recorded as unknown and **blocks** selection when the field is `licence` or when `compatibility.status == unknown`; freshness window enforced in code (registry default 90 days, social freshness 180 days already exists); every candidate needs ≥1 named alternative considered (already enforced for resources: `creative-intelligence.py:668-679`).

## 4. Design direction and traceability

Requirements ↔ references ↔ decisions must form a closed, checkable graph.

```
Need (from PROJECT.md / assessment)
  → Requirement (derived at S4B by existing code: creative-operations.py:236-314)
     → Decision (design_decision record: id, thesis link, basis ∈ {reference, research, thesis, constraint},
                 reference_ids (must be ANALYSED or USED), artifact anchor, status, gate)
        → Implementation mapping (requirement_id → source path + anchor + digest; existing: record_implementation)
           → Visual evidence (level/kind/viewport; existing: record_visual_evidence)
              → Review judgement (dimension + evidence ids; existing: record_creative_review)
```

New checks (in `design_intent_problems`):
- every requirement has ≥1 decision and every decision cites ≥1 requirement;
- every `reference`-based decision cites a reference whose state is `ANALYSED` or `USED`;
- no `USED` reference lacks a downstream decision (`used_by` — already present);
- design thesis appears verbatim in the handoff (already enforced: `ariadne.py:821-826`);
- **new:** each decision records the alternative it rejected and why (the current model requires alternatives only for *resources*).

**Human direction approval (G1) is preserved and strengthened.** G1 becomes an `Approval` bound to the digest of the locked `DESIGN.md` (03 §4), so editing the direction after approval invalidates the gate instead of silently inheriting it. The engine continues to present the direction and to stop; it never grants the gate.

## 5. Rendered QA

Source code cannot prove rendered quality. Four separate activities, never merged into one label:

| Activity | What it is | Evidence artifact | Independent of the implementer? |
|---|---|---|---|
| Functional QA | Declared project commands (`build`, `typecheck`, tests) — already executed and hashed by Ariadne's validator | command records with returncode + stdout/stderr hashes (`ariadne.py:2568-2616`) | Yes (different process from the worker) |
| Accessibility QA | Automated a11y checks (axe-core class tooling) **or** documented manual checks: keyboard traversal, focus order, contrast ratios, reduced-motion behaviour, semantics | measurement records: rule id, severity, target selector, value; manual checks need a recorded method + result | Yes if run by the validator; a tool itself must be operator-approved (new dependency ⇒ G2) |
| Visual regression | Capture at declared viewports; compare against a previous capture or a reference; report pixel/structure deltas | capture artifacts: digest, viewport, DPR, URL/route, build id; diff artifact with regions and thresholds | Yes |
| Independent design judgement | A reviewer who did not build it judges against the rubric and the approved direction | review record citing evidence ids per dimension (existing 10-dimension model) | Only if reviewer identity ≠ worker identity and the review context is the isolation-proven S5 packet (H3) |

The **instrument is opt-in and dependency-free by default**: v2 ships a `capture` adapter interface and a *fixture* implementation (deterministic, no browser) so the discipline is testable offline; real browser capture (Playwright-class) is an operator-approved optional dependency, never required, and never installed automatically. This preserves Ariadne's "no paid API, no cloud account, works offline" property.

Evidence ladder becomes instrument-backed (R5): `code-suggests` requires source anchors only; `rendered` requires a capture artifact with digest + viewport; `observed` requires an interaction/measurement artifact; `verified` requires independent re-execution evidence (e.g. the validator re-ran the capture and reproduced the digest within tolerance). A worker-written JSON flag can never satisfy `rendered`.

## 6. Refinement

Bounded, evidence-based, defect-scoped:

1. **Findings** are records: `{finding_id, kind ∈ {functional, accessibility, visual, judgement}, severity, requirement_id, decision_id, evidence_ids, what, why_it_matters, suggested_scope}`. No finding exists without evidence ids.
2. **Scope containment.** A refinement cycle names the *smallest* artifacts to change (file/component/selector). A cycle that rewrites an entire interface is refused unless the finding's `severity` is blocking *and* the finding count for that artifact exceeds the threshold — otherwise the engine must request an explicit human decision (recorded as an intervention).
3. **Bounded cycles.** Reuse the existing implementation/visual review budget: `creative-operations.py:1184-1190` stops after two iterations and requires a human decision. v2 keeps a single global notion of repair budget per stage (worker repairs `MAX_ROUTINE_REPAIRS = 2` already) so design refinement and implementation repair cannot each claim a fresh budget.
4. **Regression guard.** Every refinement cycle must re-run the previously passing functional commands and re-capture the previously passing views; a cycle that fixes a finding while breaking a passing check is reported as a regression, not as a fix.
5. **Termination.** The engine stops with a recorded reason when: all findings are resolved, budget exhausted, or two cycles produce no measurable improvement (finding count and severity unchanged). Stopping is a normal outcome; it is never recorded as success unless the criteria were actually met.

## 7. Interfaces and ownership

```python
class ReferenceAdapter(Protocol):
    id: str
    def enabled(self) -> bool: ...
    def candidates(self, query: ReferenceQuery) -> list[ReferenceCandidate]: ...
    def retrieve(self, candidate, consent) -> RetrievedEvidence: ...      # may raise Inaccessible(blocker)

class ComponentRegistry(Protocol):
    def entries(self) -> list[RegistryEntry]: ...
    def problems(self) -> list[str]: ...                                 # freshness, licence, shape
    def evaluate(self, candidate, context) -> EvaluationRecord: ...      # never installs

class CaptureAdapter(Protocol):                                          # rendered QA instrument
    id: str
    def available(self) -> Capability: ...
    def capture(self, spec: CaptureSpec) -> CaptureArtifact: ...         # digest, viewport, route
    def compare(self, a: CaptureArtifact, b: CaptureArtifact, thresholds) -> DiffArtifact: ...

class DesignReview(Protocol):
    def build_request(self, packet, rubric) -> ReviewRequest: ...
    def ingest(self, response, identity) -> ReviewRecord: ...            # independence checked here
```

Ownership: `design/` owns adapters, registry, direction traceability, rendered QA and refinement. `evidence/` owns the record schemas, hashing and provenance transitions they use. `policy/` owns the G2 authority boundary and the refinement budget. The design subsystem may *propose*; only `policy/` may authorize, and only human channels may satisfy a gate.

## 8. Non-negotiable properties

1. A paid service (Mobbin-class) is optional and never bundled; the subsystem works fully offline with local references and project documents.
2. No installation, no publishing, no external write of any kind from a design adapter.
3. No aesthetic preference is imposed globally: design direction derives from the project brief and the approved thesis, never from a personal portfolio style. (The current `DESIGN-TASTE.md` is delivered as *guidance*; v2 must keep it as guidance, not as a gate — check that no v2 rule makes a tut-taste-specific choice mandatory.)
4. Every visual claim is traceable to an artifact digest; every decision is traceable to a requirement; every requirement is traceable to the brief.
5. Nothing in this subsystem may report `verified` on the strength of a self-declared field.
