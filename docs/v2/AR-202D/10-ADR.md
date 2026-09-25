# AR-202D — Architecture decision records

Material decisions taken in this milestone, with the alternatives that were
rejected. Each record names the code that enforces the decision and the benchmark
case that would fail if it were reversed.

---

## ADR-001 — `G1D` is a separate gate for engine design-direction records

**Context.** AR-202D needs the human design-direction decision to bind an
*engine-created* constraint record (hierarchy, interaction, responsive rules,
rejected findings), not only `DESIGN.md`. AR-201 already has `G1` bound to the
`DESIGN.md` revision.

**Decision.** Add gate id `G1D` with subject type `design-direction-record`,
recorded through the existing `policy.approve` writer on the `human-cli` channel,
bound to `{direction-id, task-id, scope, constrained-body}`.

**Alternatives rejected.**

* *Reuse `G1` with a second subject type.* `policy.gate_satisfied` selects the
  latest approval for a gate; two subject types under one gate would make a
  `DESIGN.md` approval able to satisfy the direction check or vice versa,
  depending on ordering. That is exactly the class of bug AR-201 exists to
  prevent.
* *Store the approval inside the direction record.* It would bypass channel
  enforcement, identity recording and consumption, and would create a second
  authorization implementation.
* *Require no approval for the engine record.* Then the implementer's own
  direction would be self-authorizing.

**Enforced by** `policy.approve`, `contracts.GATE_SUBJECT_TYPES`,
`design.approve_direction`. **Tested by**
`design-invariants.direction-gate-is-separate`,
`design-direction.worker-cannot-self-approve`,
`design-invariants.only-the-human-channel-approves`.

---

## ADR-002 — Design records live in the run state with their own schema family

**Context.** AR-202D adds nine record collections. The published `v1.6.7` runtime
reads `ariadne-run.json` and refuses an unknown `schema_version`.

**Decision.** Keep run-state file schema `1`. Add the collections additively, with
`contracts.SCHEMA_DESIGN = 1` and `contracts.DESIGN_CONTRACT =
"ariadne-design-1"` recorded in the engine marker. `persistence.write_state`
normalises them; `state_problems` validates that they are lists.

**Alternatives rejected.**

* *Bump the run-state schema and migrate.* It would refuse the run to the
  published runtime for no benefit and would auto-migrate user projects, which
  AR-202D is explicitly forbidden from doing.
* *Store design records in a separate side-car file.* It would create a second
  evidence store that could drift from the state, and it would break the
  atomic-write and recovery guarantees the state already has.

**Enforced by** `persistence.ADAPTIVE_COLLECTIONS`, `contracts.SCHEMA_DESIGN`.
**Tested by** `design-invariants.events-join-the-canonical-chain` (a real run keeps
a readable state) and `suite.repo-self-test` / `persistence` checks (the schema
and migration contracts are unchanged).

---

## ADR-003 — An inspection type bounds the claim kinds it can support

**Context.** "I read the HTML, therefore the interaction is good" is the failure
mode AR-200's design philosophy names and could not stop.

**Decision.** Model three inspection types (`CONTENT`, `VISUAL`, `INTERACTION`) and
six claim kinds (`structure`, `content`, `appearance`, `behaviour`, `timing`,
`feedback`), with an explicit support table. A claim whose kind is outside the
support of every cited inspection is refused, both at inspection recording and at
usage.

**Alternatives rejected.**

* *One `inspected` flag.* It cannot distinguish reading from looking from driving,
  which is the entire problem.
* *Trust the worker's declared evidence strength.* That is assertion, not evidence.
* *Require every inspection type for every reference.* It would refuse the valid
  partial case (visually inspected, never driven) and would make reference research
  impossible in a normal environment.

**Enforced by** `references.INSPECTION_SUPPORTS`, `references.inspect`,
`references.mark_used`. **Tested by**
`reference-provenance.content-inspection-cannot-satisfy-visual`,
`reference-provenance.visual-inspection-cannot-satisfy-interaction`.

---

## ADR-004 — Capture provenance is method-specific and checked, not declared

**Context.** A rendered claim must not rest on a file's existence. A digest proves
integrity, not capture.

**Decision.** `render.record` requires a real capture artifact whose method has a
checkable obligation: `offline-fixture` needs the adapter-written capture manifest
beside the artifact (naming that artifact, digest and adapter), and
`declared-observer` needs the observer's explicit declaration and is capped at
`RENDERED`.

**Alternatives rejected.**

* *Trust any record that carries a matching digest.* Anyone can hash a file; the
  digest says nothing about how the file came to exist.
* *Require a digital signature.* No offline, dependency-free way to do it, and it
  would make the whole contract unverifiable in this milestone.
* *Require a real browser for everything.* It would make AR-202D untestable
  offline and would turn an optional capability into a requirement.

**Enforced by** `render._provenance_problems`, `render.record`, `render.observe`,
`render.verify` (a declared artifact cannot be promoted to `OBSERVED` or to
`VERIFIED`, because the only thing re-production could compare is a hash of the
same external file). **Tested by** `rendered-evidence.capture-provenance-required`,
`rendered-evidence.declared-observer-cannot-exceed-rendered`,
`rendered-evidence.declared-observer-cannot-be-verified`,
`rendered-evidence.offline-fixture-records-evidence`.

---

## ADR-005 — The offline fixture is a first-class capture adapter, not a browser stand-in

**Context.** AR-202D must be testable without a real browser, and must not let
fixture evidence masquerade as browser evidence.

**Decision.** Ship `OfflineFixtureAdapter`, which materialises deterministic
artifacts from a declared scene, records `environment = {"kind":
"offline-fixture", "browser": "none"}`, prefixes screenshot bytes with
`ARIADNE-OFFLINE-FIXTURE` and marks them `encoding: fixture-bytes`. Ship
`LocalBrowserAdapter` as a contract that reports itself unavailable unless an
authorized local capability is configured; nothing installs or starts a browser.

**Alternatives rejected.**

* *Bundle a headless browser.* A new dependency, a new network surface and a new
  failure mode, for a milestone whose claims do not need it.
* *Let the fixture claim to be a browser run.* It would make the strongest claims
  in the milestone unfalsifiable.
* *Skip rendered evidence entirely.* Then "the rendered result satisfies the
  direction" would remain an assertion.

**Enforced by** `render.OfflineFixtureAdapter`, `render.LocalBrowserAdapter`,
`routing.route_evidence`. **Tested by**
`rendered-evidence.offline-fixture-records-evidence`,
`rendered-evidence.browser-capability-reported-honestly`,
`design-invariants.evidence-routing-never-guesses`.

---

## ADR-006 — Optional paid providers are contract-only

**Context.** Mobbin-class libraries hold useful design references, and AR-202D is
forbidden to require paid access, bypass authentication or redistribute
proprietary assets.

**Decision.** Implement the adapter contract and the honest refusal. A provider is
usable only through an explicitly configured licensed interface with a licence
reference; otherwise every call is a recorded `INACCESSIBLE` with a blocker.
Ariadne provides the whole workflow without it.

**Alternatives rejected.**

* *Scrape the provider's public pages.* Explicitly forbidden and technically a
  different (unlicensed) product.
* *Make the provider required for reference research.* It would make the milestone
  unusable in a normal environment and would gate design work on a purchase.

**Enforced by** `references.OptionalProviderAdapter`. **Tested by**
`reference-adapters.inaccessible-result-recorded-honestly`,
`reference-adapters.gated-source-is-not-bypassed`,
`reference-adapters.unsupported-capability-stays-unsupported`.

---

## ADR-007 — Requirement closure thresholds depend on the claim kind

**Context.** "Navigation remains reachable at 320 px" cannot be verified from
source, while "use a semantic `<button>`" can. Treating all requirements alike
would either over-demand evidence or accept a code listing as proof of quality.

**Decision.** Each requirement declares `evidence_kind` (`source`, `rendered`,
`behavioural`) and the minimum evidence strength for `observed` and `verified`
follows from it: source may close from source evidence, rendered needs a capture,
behavioural needs an observation, and `verified` needs independent re-production
(or, for source claims only, an independent review that covers the requirement).
Stale evidence closes nothing.

**Alternatives rejected.**

* *Require rendered evidence for everything.* It would refuse valid static
  claims and make every small task expensive.
* *Accept source for everything.* It is exactly the "the code exists therefore it
  works" fallacy.
* *Score requirements.* There is no defensible calibration for a score, and it
  would be a number nobody could check.

**Enforced by** `design.record_requirement`, `design.stale_requirements`,
`policy.design_evidence_requirement`. **Tested by**
`requirement-closure.source-evidence-sufficient-for-source-claim`,
`requirement-closure.rendered-requirement-cannot-close-from-source`,
`requirement-closure.stale-artifact-invalidates-verification`.

---

## ADR-008 — Design refinement shares the engine's single repair budget

**Context.** AR-202 bounds automatic repair (`policy.MAX_ROUTINE_REPAIRS = 2`) per
stage. A design refinement loop is the obvious place for a second, unbounded budget
to appear.

**Decision.** `critique.MAX_DESIGN_REFINEMENTS = 2` (the same number), the budget
is per task and per finding, and `refinement_budget` also reports the
worker-repair state, so a run cannot spend a design budget and an implementation
budget on the same defect. Exhaustion is reported as `REFINEMENT_LIMIT_REACHED`
and requires a human decision.

**Alternatives rejected.**

* *A separate design budget.* It doubles the number of automatic attempts on the
  same defect without any evidence that two more would help.
* *No automatic refinement at all.* Then findings would accumulate with no
  mechanism to close them, and "refinement fixed the finding" could not be
  recorded.

**Enforced by** `critique.refinement_budget`, `critique.propose_refinement`,
`policy.design_evidence_requirement`. **Tested by**
`design-refinement.repair-limit-enforced`,
`design-refinement.unresolved-finding-remains-visible`.

---

## ADR-009 — Evidence routing is a routing decision, not a new axis

**Context.** A design task may need evidence no configured adapter can produce.
The engine must not guess, and must not invent a second routing model.

**Decision.** `routing.route_evidence` produces a normal routing decision in the
existing `routing_decisions` collection, using the existing rules and the single
new rule id `design-evidence-unavailable`. Capabilities come from adapter
*declarations* (`capabilities()`/`available()`), never from a model or vendor name.
Needs that only deepen the work are recorded as opportunities and never block.

**Alternatives rejected.**

* *Infer capability from the model name.* It is unverifiable and would make
  routing a branding question.
* *Fail the whole stage when optional evidence is missing.* It would block
  reference research in every environment without a browser driver.
* *Silently proceed without the evidence.* It is the assertion mode AR-202D
  exists to remove.

**Enforced by** `routing.route_evidence`, `routing.DESIGN_EVIDENCE_REQUIREMENTS`,
`routing.DESIGN_OPTIONAL_EVIDENCE_NEEDS`. **Tested by**
`design-invariants.evidence-routing-never-guesses`,
`design-invariants.events-join-the-canonical-chain`.

---

## ADR-010 — One new failure class, everything else maps onto existing ones

**Context.** The brief lists eleven possible design-specific failures. AR-202
already has a taxonomy with explicit retry/strategy/escalation flags.

**Decision.** Map thirteen design *kinds* onto existing classes
(`execution.DESIGN_SOURCE_KINDS`) and add exactly one new class,
`DESIGN_FAILURE`, for a design-workflow limit that no existing class models
(`REFINEMENT_LIMIT_REACHED`). Unknown stays `UNKNOWN`.

**Alternatives rejected.**

* *One class per design kind.* It duplicates the taxonomy and splits the retry
  policy across two vocabularies.
* *No new class.* `REFINEMENT_LIMIT_REACHED` is not an implementation, validation,
  review, capability, context or authorization failure, and calling it one would
  mislead every consumer of the flags.

**Enforced by** `contracts.DESIGN_FAILURE_KINDS`, `execution.DESIGN_SOURCE_KINDS`,
`execution.FAILURE_FLAGS`. **Tested by** the `evidence-and-failures`/`security`
AR-202 cases (unchanged) and `design-invariants` (the design kinds are declared
and validated).

---

## ADR-011 — Design context rules are declarations, never repository inference

**Context.** AR-202's context rules could not express "this source is design
material and this task is not a design task". The obvious shortcut — treat the
presence of front-end files as a design signal — would pull references into every
task in a repository that happens to contain a component directory.

**Decision.** A source *declares* `requires: design` or `requires: reference`, and
is omitted with `IRRELEVANT_TO_TASK` unless the run's design characterisation says
the task needs it. `RELEVANT_CHANGED_FILE` is available for artifact-anchored
sources. Task evidence is the request text and the handoff's declared scope rows —
never the repository listing.

**Alternatives rejected.**

* *Infer from the repository.* It makes depth depend on unrelated files, which the
  brief forbids, and the characterisation benchmark asserts the opposite
  behaviour for a backend task in a repository full of components.
* *Add design sources to all packets and let the worker ignore them.* It grows
  every packet and weakens isolation for no benefit.

**Enforced by** `context._design_reason`, `context.design_source_state`. **Tested
by** `design-invariants.context-isolation-preserved`.

## ADR-012 — Trust boundaries are canonical containment, atomic refusal and bounded collections

**Context.** The AR-202D-H review found that several engine operations accepted a
caller-supplied path and hashed it into provenance without checking where it
resolved; that reference transitions wrote their payload before validating the
move, so a refused call left partial state; that the documented direction contract
was enforced only in part; that a scope check used a substring rule; that every
characterisation walked the whole project tree; that seven authoritative
collections were unbounded; and that an exported capability vocabulary was never
consulted and had already drifted. Each was a case of a value the caller supplies
standing in for a value the engine checks.

**Decision.**

* **Containment is canonical and precedes trust.** `contracts.resolved_within`
  resolves the path (folding `..`, separators, drive qualification and
  symlinks/junctions) and compares membership case-insensitively on Windows, where
  the filesystem does. String-prefix tests on unresolved input are not used
  anywhere. Project-scoped evidence must resolve inside the project; captured
  evidence inside the run's capture root; the one deliberate exception is a
  `declared-observer` artifact, which is external by design and must carry the
  observer's declaration, so its provenance says out loud that the engine did not
  produce it.
* **A refusal is atomic.** A lifecycle move validates the move *and* the intended
  record before anything is written, so `ContractError` keeps its promise that
  nothing changed and a refused call cannot advance provenance. Recording
  functions pass their payload as updates to one commit point rather than mutating
  first and asking afterwards.
* **Authority vocabularies have exactly one definition and one consumer.**
  `DIRECTION_SECTIONS` drives direction validation; `path_matches` is the single
  scope rule shared with the runtime's worker scope check; `DESIGN_CAPABILITY_IDS`
  is validated against the routing tables at every `route_evidence` call.
* **Bounds are hard and explicit, never silent.** `MAX_DESIGN_RECORDS` (10 000 per
  authoritative collection) and `MAX_REFERENCE_HISTORY` (100 transitions) refuse
  with an error instead of truncating evidence. `require_design_capacity` also
  refuses a key outside `DESIGN_COLLECTION_KEYS`, so a typo cannot silently skip
  the bound. A full record is ≈1.5 KB, so the bound is ≈15 MB of run state: far
  above a plausible single-task workflow, far below a pathological one.
* **The project scan is pruned, deterministic and bounded before work is done.**
  Excluded directory names are matched case-insensitively (the filesystems this
  runtime targets are), reparse points are not followed, and directories *and*
  their listings are counted against `MAX_STYLESHEET_SCAN_DIRECTORIES` /
  `MAX_STYLESHEET_SCAN_ENTRIES` before any listing is sorted, so no single
  directory can make the scan do unbounded work. When a bound trips, the evidence
  says the scan was bounded rather than implying completeness.
* **Each new guard is verified by mutation.** A guard that cannot fail is not a
  guard: for every fix in this pass the fix was reverted in memory, the guard was
  re-run, and it failed (see `07-TEST-RESULTS.md` §8).

**Alternatives rejected.**

* *Prefix string checks after `os.path.abspath`.* They miss case variation,
  symlink escapes and prefix collisions (`project` vs `project-evil`), which is
  exactly what the review reproduced.
* *Rollback after a failed write.* It hides the failure mode the invariant exists
  to prevent; pre-validation is simpler and total for these records.
* *Capping collections by keeping the latest N records.* Authoritative evidence
  must not be silently dropped; a bounded refusal is honest, a truncated ledger is
  not.
* *A second ignore-file dialect for the project scan.* The exclusion list is one
  explicit tuple of dependency/build/runtime directories; a second policy would
  need its own tests and could disagree with the first.

**Enforced by** `contracts.resolved_within`, `contracts.contained_evidence_path`,
`contracts.contained_evidence_path_any`, `contracts.permitted_project_root`,
`contracts.path_matches`, `contracts.require_design_capacity`,
`references._transition`, `render.permitted_evidence_path`,
`design._stylesheet_paths`, `routing.evidence_vocabulary_problems`. **Tested by**
the engine-core hardening checks and the `design-hardening` benchmark group
(`07-TEST-RESULTS.md` §8), with mutation checks confirming each guard can fail.
