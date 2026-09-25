# AR-203 — Capability Registry

AR-202 routing consumed *declared* adapter capabilities: an adapter said what it
could do and routing believed it. AR-203 keeps the declaration and adds the
evidence around it, because three different facts were collapsing into one:

```text
capability declared  ≠  capability available now  ≠  capability exercised successfully
```

## 1. Evidence states

`contracts.CAPABILITY_STATUSES`:

| Status | Meaning | Established by |
|---|---|---|
| `DECLARED` | the adapter says it supports it; nothing was checked | `capabilities.declare` |
| `DISCOVERED` | the surface exists (a method, an executable on PATH) | a probe |
| `AVAILABLE` | a deterministic probe established it can be used here | a probe |
| `EXERCISED` | it produced a result in an engine execution or a recorded probe artifact | `observe` with an execution or probe evidence |
| `VERIFIED` | an existing verification record reproduced the exercised result | `observe` with a `CURRENT` verification record at `REPRODUCED`+ |
| `UNAVAILABLE` | it cannot be used here, with a recorded reason | a probe or an observation |
| `UNKNOWN` | nothing established it | the default |

`contracts.CAPABILITY_STATUS_ORDER` ranks them for comparison;
`UNAVAILABLE` and `UNKNOWN` rank with nothing, because neither satisfies a
capability requirement.

A declaration can never become `VERIFIED`: `capabilities.observe` refuses a
`VERIFIED` status unless it cites an existing verification record whose level is
`REPRODUCED` or stronger and whose freshness is `CURRENT`. `EXERCISED` requires
either the engine-created execution that exercised it or a probe artifact with a
recorded output digest.

## 2. Records

`capabilities.declare(...)` writes a `capability_records` row with
`schema_version = contracts.SCHEMA_CAPABILITY`, the capability id, the adapter and
family, the status, the mechanism, the reason, evidence rows, the surface
fingerprint, version/provider/model/runtime, the execution or verification it
cites, the observer, and the timestamp.

`capabilities.observe(...)` writes the same shape for anything above a
declaration, with the obligations above enforced. Both re-hash every evidence
artifact they can read and refuse an artifact that changed after observation. A
later observation for the same `(family, adapter, capability)` marks earlier
`CURRENT` rows `SUPERSEDED`; history is kept.

`capabilities.capability_status(state, family=, adapter=, capability_id=, declared=)`
resolves the newest observation. Without a registry record the answer is
`DECLARED` when the adapter itself declares the capability and `UNKNOWN`
otherwise — never `UNAVAILABLE` without evidence and never `VERIFIED` from a
declaration. `SUPERSEDED` and `STALE` resolve to `UNKNOWN` for a current
requirement.

## 3. Deterministic probes

No probe makes a network call, installs anything or invokes a paid service.

| Probe | What it establishes | Status |
|---|---|---|
| `ExecutableProbe(command)` | whether the executable resolves on PATH (`shutil.which`; no process started) | `AVAILABLE` / `UNAVAILABLE` |
| `AdapterMethodProbe(adapter, capability)` | whether the adapter declares the capability and the mapped method is callable | `AVAILABLE` / `DISCOVERED` / `UNAVAILABLE` |
| `FixtureCommandProbe(argv, cwd, ...)` | one declared command runs in an isolated fixture to an expected exit code, with stdout/stderr digest recorded | `EXERCISED` / `UNAVAILABLE` |

`capabilities.run_probe(state, probe)` runs one probe and records the
observation. A capability that cannot be checked without external cost or side
effects is recorded honestly as `DECLARED`, `AVAILABLE` or `UNKNOWN` — the
registry never makes a paid call to turn a status green.

## 4. Routing integration

`routing.route_evidence(..., evidence_policy=...)` accepts:

| Policy | Requirement | Intended use |
|---|---|---|
| `declared` (default) | the declared capability suffices; an observed `UNAVAILABLE` still blocks | historical behaviour, low-stakes work |
| `observed` | at least `AVAILABLE` from a deterministic probe | medium-stakes work |
| `strict` | `EXERCISED` or `VERIFIED` with `CURRENT` freshness | high-stakes work |

The policy is recorded on the routing decision (`evidence_policy`) and on every
candidate (`capability_evidence`, `evidence_policy`), and each exclusion names the
policy it failed. A candidate known to lack the capability is excluded; a
candidate whose capability is `UNKNOWN` is excluded under `observed` and
`strict` and allowed under `declared` (which is exactly what a declaration is
for). `capabilities.satisfies(status, freshness, policy=)` is the single
implementation of the rule; routing does not duplicate it.

The CLI exposes the policy as `design-plan --evidence-policy
declared|observed|strict`.

## 5. Tests

Engine suite: `a declaration alone is never a verification`,
`a deterministic probe establishes availability`,
`a missing executable is observed unavailable with a reason`,
`an exercised capability needs a real execution or probe artifact`,
`an exercised capability records the engine execution that exercised it`,
`a capability cannot be verified without an existing verification record`,
`routing consumes declared capabilities under the declared policy`,
`an observed-unavailable capability is excluded from routing`,
`the strict policy does not accept a declaration`.

Benchmark group `capability-registry`:
`declared-is-not-verified`, `exercised-requires-real-execution`,
`unavailable-excluded-from-routing`, `evidence-policy-is-explicit`,
`deterministic-probes-are-honest`.

## 6. What is not claimed

No live provider capability was verified in this milestone: no paid endpoint was
called and no external model was asked anything. Capabilities that require an
external service remain `DECLARED` or `UNKNOWN`, and the routing policies that
need stronger evidence treat them accordingly. That is the honest state, not a
gap to paper over.
