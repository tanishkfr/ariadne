# AR-202D — Milestone report

## 1. What this milestone is

AR-200 designed Ariadne's design intelligence and deferred it. AR-201 built the
executable orchestration and authorization core. AR-202 added adaptive context,
executable routing, execution provenance, recovery and structured engine events.

AR-202D makes the design process itself inspectable. The engine can now establish,
from recorded evidence rather than from prose:

* what design problem is being solved and how deep the design work needs to go;
* what references were found, which were reachable, which were inspected, what was
  learned, and which findings influenced a decision;
* which existing project component already solves part of the problem and whether
  a new dependency is justified;
* what design direction was approved, by whom, at which revision;
* whether implementation matches the direction, and what the rendered product
  actually looked like at which viewport and revision;
* what an independent critique found
  and whether refinement fixed it without breaking something else.

It is **not** "make the AI more creative". Nothing in the milestone scores,
judges or generates design taste.

## 2. What changed

Fifteen code surfaces, none of them a new dependency:

* five new engine modules (`design`, `references`, `components`, `render`,
  `critique`, ~4 470 lines with their contracts);
* eight existing engine modules extended in place (`contracts`, `events`,
  `execution`, `routing`, `context`, `policy`, `persistence`, `api`);
* the runtime gained five additive commands
  (`design-plan`, `record-design`, `design-check`, `design-report`,
  `approve-design-direction`);
* the engine-core suite gained 59 design checks; the benchmark suite gained 58
  cases in 11 groups.

## 3. The seven claims the milestone makes, and what supports each

| Claim | Mechanism | Evidence |
|---|---|---|
| design depth is selected, not assumed | `design.characterize` + `select_pipeline`, every characteristic carrying source and evidence | 6 characterisation cases, 52 engine checks |
| a reference has provenance | ordered lifecycle, inspection evidence, claim-kind bounds, usage anchors | 8 provenance cases |
| component choice is project-aware | minimum-solution ladder, mandatory alternatives, blocking unknown obligations, human-only install authority | 5 component cases |
| a design direction constrains implementation | engine-created record, `G1D` human approval, section-level revision fingerprint | 5 direction cases |
| rendered claims need rendered evidence | five distinct evidence states, method-specific provenance, revision and viewport binding, verification by re-production | 6 evidence cases |
| critique is independent | two engine-created executions, direction revision binding, evidence-bound findings, four separate QA activities | 5 critique cases |
| refinement is bounded and scoped | defect-scoped plans, scope enforcement, re-evidence obligation, one shared repair budget | 6 refinement cases |

Plus 7 trust-invariant cases and 1 measurement case covering gate separation,
channel enforcement, no-install, source-vs-rendered strength, event chain
integrity, context isolation and evidence routing.

## 4. Design decisions worth reading

Nine architecture decisions are recorded with their rejected alternatives in
`10-ADR.md`. The three that shape the milestone most:

* **ADR-001** — `G1D` is a separate gate. `G1` authorizes `DESIGN.md`; `G1D`
  authorizes the engine's constraint record; neither can substitute for the other.
  Reusing `G1` would have made an approval order-dependent, which is exactly the
  class of bug AR-201 exists to prevent.
* **ADR-004** — capture provenance is method-specific and checked: an
  `offline-fixture` artifact needs the adapter-written capture manifest, and a
  `declared-observer` artifact needs an explicit declaration and is capped at
  `RENDERED`. A digest proves integrity, not capture.
* **ADR-007** — closure thresholds depend on the claim: a source-level requirement
  may close from source evidence, a rendered one needs a capture, a behavioural
  one needs an observation, and `verified` needs independent re-production.

## 5. What deliberately did not change

* `VERSION` stays `1.6.7`; no tag, no release, no push, no remote write.
* The published `v1.6.7` runtime keeps reading the run state: file schema stays
  `1`, design records carry their own schema family, and nothing auto-migrates.
* Every existing CLI command, stage name, gate name and packet contract still
  behaves exactly as it did; the new commands are additive, and `--gate` still
  accepts exactly `G1/G2/G3`.
* The creative ledgers (`creative-intelligence.py`, `creative-operations.py`) are
  read, not replaced. The operations ledger's requirements remain the canonical
  requirement set the closure model checks.
* Approval authority is unchanged: `policy.approve` is still the only writer, and
  the implementer still cannot approve anything.
* Context isolation is unchanged: the design context rule only *omits* sources and
  never adds one, so a design source cannot appear in a role that should not have
  it.
* No model calls, no network, no installs, no paid service, no Boreal change.

## 6. Honest limits

* **No live verification of anything external.** Web references, browsers and
  design databases are all contract-and-refusal-only in this environment. The
  milestone's strongest claims are `DETERMINISTIC_VERIFIED`; `LIVE_VERIFIED` is
  empty.
* **Offline fixtures do not measure human aesthetic quality.** They test the
  engine's evidence logic. No case asserts that a design is good.
* **Capability statements are declarations.** `LocalBrowserAdapter` and the
  optional provider report themselves unavailable; the engine records that
  honestly, and the design evidence route blocks rather than guessing. When a live
  capability exists in a future environment, the same route will select it —
  which is exactly the AR-203 hardening question.
* **Two independent reviews hardened the ingest boundary** before completion. The
  first closed seven gaps where a caller-supplied value could stand in for an
  engine-checked one, and found two CLI defects (a review crash and two false
  structural problems) by driving the command path end to end. The second (the
  AR-202D-H hardening pass) reproduced and closed the seven findings it had
  recorded as open: path containment for usage/source/observation artifacts,
  validate-before-mutate ordering in the reference lifecycle, structural
  enforcement of every required direction section, the shared scope matcher, the
  bounded project scan, collection bounds, and the unused capability vocabulary.
  See `07-TEST-RESULTS.md` §6 and §8.
* **One environmental flake was found by this milestone's own testing and
  fixed**: a Windows directory-swap lock in the installer, now retried through the
  launcher's existing `replace_with_retry` helper. No assertion was weakened; see
  `07-TEST-RESULTS.md` §3.
* **Per-task depth is only as good as the request and scope text.** The
  characteriser is deterministic and evidence-bearing, and it will be wrong when
  the declared scope is wrong; that is why every characteristic records the
  evidence it used and why a human can override it with `declared` input.

## 7. Result

**0 FAIL, 0 ERROR** across the full required suite:

* `benchmarks/run_benchmarks.py`: **157 cases, 152 PASS / 0 FAIL / 3 OBSERVED /
  0 ERROR / 2 DECLARED_SKIP**, with the AR-202 subset at exactly its reported
  87-case classification (83 / 0 / 2 / 0 / 2) — no regression, no weakened
  assertion;
* `scripts/test-engine-core.py`: **246/246** (205 before the hardening pass);
* fourteen repository suites: all pass;
* 462 benchmark checks with pass/fail semantics, 415 passed, 0 failed.

AR-202D is complete when Ariadne can show not only what design was produced, but
what informed it, what evidence supports it, whether the rendered result satisfies
the intended direction, what an independent critique found, and whether refinement
actually fixed those findings. Each of those is now a record with a subject, a
revision and an author — and each refusal that keeps it honest is a passing case.

## 8. Where the next milestone starts

`09-AR-203-HANDOFF.md` is the implementation-ready handoff. In one line: AR-203
should harden independent verification — a live-capability registry bound to the
declared adapters, independent design-verification executions with pinned
identity, and confirmation that the design contracts hold against a real browser
and a real reference provider without weakening any invariant AR-202D proved
offline.
