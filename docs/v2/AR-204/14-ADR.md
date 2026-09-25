# AR-204 — Architecture Decisions

Durable decisions only. Each one is enforced by code the suite exercises.

## ADR-001 — Economics measures the task, and a failed attempt is part of it

**Context.** AR-203 recorded usage on one execution. A retry made a task look
cheaper than it was, because the failed attempt's usage sat on an execution nobody
summed.

**Decision.** `economics.task_cost` sums every execution attributed to a task,
including failed and abandoned ones, and reports `failed_executions` and the
failed-node usage separately. `verified_completion_cost` returns a verified figure
only when an AR-203 verification at `VERIFIED` covers the task; otherwise it
returns `cost_of_unverified_attempt`, a deliberately different label.

**Consequences.** A repair cannot be made to look free, and the milestone's
primary metric can never be reported for a task that was not verified. Mutation
M3 removes the failed attempt from the sum and the protecting case fails.

## ADR-002 — Monetary cost is either measured or derived, never invented

**Context.** Provider prices change and a hard-coded rate becomes a false fact.
A token count is not a price.

**Decision.** Two channels exist and they never merge. `record_billing` stores a
provider- or adapter-reported amount with the observer named, and refuses a worker
or self-reported source. A price profile is registered as data with its own source
and effective date, versioned by the canonical digest of its content, and a figure
computed from it is labelled `DERIVED` with the profile id. `cost_from_usage`
lists tokens that no profile price covers instead of treating them as free. With
neither channel, monetary cost is `UNKNOWN`.

**Consequences.** No routing or authorization path may read a price profile, and
the engine's own arithmetic is tested with synthetic prices only. Invariant 47 is
enforced by construction.

## ADR-003 — Cache telemetry keeps structural cacheability out of the hit column

**Context.** A request whose stable prefix is large is *cacheable*; it is not
cached. Reporting a hit from structure would fabricate a measurement and would make
a run look cheaper for no reason.

**Decision.** `record_cache_observation` stores measured provider metadata and
structural facts in separate fields. `cache_hit` stays `None` unless a provider
reported it, the record's note says so, and a mutation that fills the hit column
from structure is detected by the engine suite.

**Consequences.** A provider without cache reporting still yields useful structural
data, and no reader can mistake it for a hit.

## ADR-004 — Output externalization is storage, and the artifact is the evidence

**Context.** The runtime kept a digest of a validation command's output and
discarded the bytes. That protects the model's active context at the cost of the
evidence.

**Decision.** A large output is written whole to `evidence/artifacts/<sha256>.log`;
the model-facing view is a bounded head and tail plus a reference; retrieval
re-hashes before returning and refuses a mismatch. The threshold defaults below
every measured packet and above every measured small artifact, and small output is
left completely untouched. The run state keeps references, never the bytes.

**Consequences.** Evidence survives, the model view is bounded, and the one
default-on setting in the efficiency policy only adds storage. Mutation M4
truncates the artifact and the protecting case fails.

## ADR-005 — History compaction is structural, archived and refuses to lose state

**Context.** Compaction is the classic place where a run loses the thing it needs:
the unresolved work item, the authorization, the failed approach it would repeat.

**Decision.** Eight entry kinds are protected and carried verbatim: task state,
unresolved work, decision, authorization, evidence reference, failed approach,
revision and verification state. Every other entry becomes one deterministic line
with its digest and first line. The complete history is archived first and its
digest recorded; retrieval re-hashes. A plan that would drop a protected entry, or
that claims a summary replaces the history, is refused. The whole feature defaults
to off.

**Consequences.** A stale or compacted view can never erase something a
continuation depends on, and enabling the feature remains a separately measured
step.

## ADR-006 — Behaviour-sensitive optimisations are flags with recorded digests

**Context.** Prompt reduction, tool deferral, compaction and path changes alter
what a model sees or how work is routed. Shipping them because they reduce bytes is
the failure mode the milestone brief names first.

**Decision.** Eight settings exist, seven default to the pre-AR-204 behaviour, and
the configuration is stored on the run state with a digest. The API refuses an
unsupported value, the CLI exposes every setting, and the prompt audit refuses to
invent a shorter stage prompt without a live evaluation.

**Consequences.** A release with every flag at default behaves as AR-203 did while
still recording the newer measurements, and any future default change can be
traced to the run that justified it.
