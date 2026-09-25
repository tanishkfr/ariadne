# ADR-0210 — Execution identity is created at the engine boundary

Status: accepted (AR-202)
Deciders: AR-202 implementation
Evidence: `src/ariadne_engine/execution.py`, `02-EXECUTION-IDENTITY.md`, benchmark group `execution-identity`

## Context
AR-201 bound approvals and reviews to identity *labels* (`--identity`, `--reviewer-identity`) that the caller supplies. Those strings are necessary but not sufficient: a label cannot distinguish two runs that used the same label, cannot tell whether the result came from the execution the engine prepared, and cannot survive a replayed return. The obvious over-correction — OS authentication, process isolation — is out of scope and would be a false claim in a single-user, single-machine runtime that cannot observe its provider.

## Decision
The engine creates one *execution identity record* per boundary it prepares or ingests, at the moment it does so:

- the id is generated (`exe_<utc>_<hex>`); no API accepts a caller-chosen id;
- it binds run, task (packet), role, adapter invocation, a nonce, the parent execution and a revision digest (project baseline + packet id + packet digest);
- lifecycle: `REQUESTED → CREATED → STARTED → OBSERVED → COMPLETED | FAILED`, with `UNKNOWN` when the runtime cannot observe;
- identity is split three ways: **requested** (what the run declared), **reported** (what a worker claims in its own output, kept as untrusted provenance) and **observed** (only written by an engine-side observer; a worker value is refused rather than promoted);
- results, validations and reviews must name an execution the engine created, be in an acceptable state, and match the boundary's revision.

Reviews additionally record `reviewer_execution` and `implementing_execution`, so `implementing_execution != reviewing_execution` is a machine-established fact rather than a claimed label.

## Alternatives considered
- **Cryptographic signing of results.** Rejected: there is no key custody or trust anchor on this machine, so a signature would imply a guarantee the runtime cannot provide. Digests and engine-bound ids give tamper *evidence*, not authentication.
- **Accepting a caller-supplied id when it looks valid.** Rejected: the forged-id test exists precisely because a caller choosing its own provenance defeats the purpose.
- **Recording "observed" model identity from the worker handoff.** Rejected as dishonest: the handoff is worker prose. It is recorded as *reported*.
- **Refusing legacy states that have no execution records.** Rejected: AR-201 runs continue without migration; an execution identity is *adopted* at ingestion time and marked as adopted, so no claim is made about how it was prepared.

## Consequences
- Provenance is engine-bound for new work and explicitly adopted (never fabricated) for work that predates AR-202.
- `observed` is `UNKNOWN` on this runtime, permanently, until a runtime exists that can report its own provider/model. Unknown stays unknown.
- Requested-vs-reported mismatches are always recorded; they *refuse* only when the run pinned a concrete model identity, because only then does a mismatch contradict an instruction the run was authorized under.
- Nothing here authenticates a person, isolates a process, or provides an OS sandbox.
