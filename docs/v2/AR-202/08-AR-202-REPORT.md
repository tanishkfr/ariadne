# AR-202 — Milestone report

Milestone: AR-202 (adaptive execution intelligence)
Baseline: AR-201 `v2/ar-201-core` @ `8844b1a`
Branch: `v2/ar-202-adaptive-execution`
Result: **87 benchmark cases — 83 PASS, 0 FAIL, 2 OBSERVED, 0 ERROR, 2 DECLARED_SKIP; repository suites unchanged and passing; 0 model calls, 0 cost**

## 1. What AR-202 changed

Ariadne can now answer, with evidence and without a model call:

* what kind of task this is, how difficult it is, what is at stake and which capabilities it needs (§`routing`);
* which context a boundary actually needs, why each candidate source was included or omitted, and which of those sources did not have to be re-hashed (§`context`);
* which available runtime satisfies the requirements, in what order the candidates were eliminated, and what happens on fallback (§`routing`);
* what actually executed: an engine-created execution identity bound to task, role, adapter invocation, nonce and revision — with requested, reported and observed identity kept strictly apart (§`execution`);
* how a failure is classified and whether it permits retry, a strategy change or escalation (§`execution`, `recovery`);
* which known interruption states can be resolved safely, by which action, with what authorization and what rollback (§`recovery`);
* what the engine decided and observed, in one append-only structured event log that existing telemetry and logs project from (§`events`).

Nothing about authorization changed except to become stricter: the S4A→S4B and
S4B→S5 evidence gaps AR-201 disclosed are closed, and reviews are now bound to
two distinct engine-created executions.

## 2. Verification in one paragraph

The AR-201 62-case benchmark suite was reproduced before any change (59 PASS /
0 FAIL / 1 OBSERVED / 0 ERROR / 2 DECLARED_SKIP) and is intact at the end
(identical classification inside the 87-case run). 25 new deterministic cases
cover adaptive context, routing, execution identity, recovery and continuation
evidence — 24 PASS and 1 measurement observation, with zero failures and zero
errors. `test-engine-core.py` grew from 96 to 145 checks and passes; every
repository suite (`check.py --self-test`, the runtime/transport/reasoner
self-tests, distribution, release, real-project, social, writing and validation
suites) passes. No model provider was contacted.

## 3. The five systems, and how each is executable rather than decorative

| System | Executable effect |
|---|---|
| Execution identity | Results, validations and reviews are refused unless they name an engine-created execution that matches role, task, revision and state; the review record carries `implementer != reviewer` as a machine fact |
| Adaptive context | The plan changes what the transport delivers (omissions, duplicate suppression) and what it re-hashes; forbidden sources cannot be added; without a plan the packet is byte-identical to AR-201 |
| Executable routing | The S4B worker role written into the packet is the router's choice; a `no-route`/`blocked` route pauses before a packet exists; a blocking failure class prevents a blind repeat |
| Failure-aware recovery | Four safe actions flow through the authoritative transition boundary or an explicit file quarantine, each with identity, reason, evidence and a byte-identical state backup; everything ambiguous is refused |
| Execution measurement | One canonical event log with a digest chain; per-boundary context/route/execution records; a measurement case reporting medians and ranges |

## 4. Notable engineering decisions

* Adaptive records carry their own schema family (`SCHEMA_ADAPTIVE = 1`), so
  AR-201 run states stay readable and continuable **without** a migration, and
  the authorization record contract did not move.
* `plan_sources` in the transport is the *only* implementation of source
  selection; the engine decides around it, and a plan that tries to omit a
  required source is refused by the compiler.
* Execution identity is engine-generated; a caller-supplied id is verified and
  never quietly replaced. A worker claim is `reported`, never `observed`.
* An identity mismatch refuses only against a *concrete* declared model;
  placeholders (`provider default - unverified`) are recognised, so honest runs
  are not punished.
* A rejection is recorded as a human decision that consumes no approval.
* Six new ADRs record these decisions (`docs/v2/AR-202/adr/`).

## 5. Costs and honest limits

* Context savings on the current fixtures are modest: optional-source omission,
  duplicate suppression and 40 334 bytes of avoided re-hashing. The measured
  preparation-time difference is within the range and therefore **not** claimed
  as an improvement — the dominant cost is the project snapshot and packet
  assembly, not hashing.
* Routing is verified deterministically against the adapter contract. Live
  provider behaviour is unverified, and no claim is made that a real provider
  honours a route.
* Observed runtime identity does not exist on this runtime; it is `UNKNOWN`.
* Recovery understands four interruption shapes and refuses the rest by design.
* The T1 tightening means a run that never recorded its S4A planning / S4B QA
  evidence now pauses at the boundary instead of proceeding. That is the point
  of the milestone; the fixtures record the evidence where a live session does.
* No OS sandbox, no process isolation, no user authentication, no cloud, no
  new dependency, no product-version change, no Boreal modification.

## 6. Where this leaves the roadmap

AR-202 delivers the adaptive execution layer the AR-200 plan called for:
justified effort, minimal context, evidence-bound provenance, classified
failures, explicit recovery and measurable behaviour. `09-AR-202D-HANDOFF.md`
lists exactly what the Design Intelligence milestone inherits, what remains
unverified, and the order in which to start. AR-202D is not started.
