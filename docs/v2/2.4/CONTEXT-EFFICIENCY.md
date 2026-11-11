# Context Efficiency �?" Ariadne 2.4B

**Policy:** AR-202 adaptive context remains the owner of inclusion decisions.
2.4B adds a measured reduction profile, revision binding, byte accounting and a
revision-bound continuation projection. It does not add a second memory store.

## 1. What was already there

`ariadne_engine/context.py` already decided every candidate source as included or
omitted with a machine-readable reason, omitted design sources from non-design
tasks, deduplicated identical content and reused source hashes from a bounded
per-run cache. The cache was already invalidated by size, mtime, stage, policy
version and revision.

The prepare-stage transport already recorded the delivered/omitted outcome in the
packet manifest. What the decision did not record was the **revision the decision
belonged to**, the **measured bytes** it included or omitted, and a
**continuation view** that a new worker session could trust without the old
conversation.

## 2. What 2.4B adds

### 2.1 Revision binding and stale refusal

Every context decision now records `revision_hash` and the final packet digest.
`context.stale_problems()` and `context.require_current()` refuse a decision
whose revision or packet digest moved. A recorded decision is evidence of one
preparation, not a reusable authorization.

### 2.2 Measured bytes, not token estimates

Candidate files are measured with `stat`, and the final decision records
`included_bytes` and `omitted_bytes`. Packet size is measured from the packet
file. No tokenizer is invented, no token count is estimated from characters, and
`UNKNOWN` stays distinct from zero.

### 2.3 Adaptive reduction, off by default

`context_reduction=adaptive` adds one conservative rule:

> an unchanged literal scope file that the request does not name is not
> re-delivered; it remains inside the permitted scope and the worker can read it
> in place.

Never omitted by this rule: the task contract, the original request, mandatory
selected method documents, canonical policy, project memory, external approved
methods, or any source the stage marks required. The reason recorded is
`OPTIONAL_NOT_SELECTED` with the evidence that the file remains readable in
place. `off` keeps every AR-202 decision exactly as before.

### 2.4 Continuation projection

`ariadne_engine/continuation.py` builds a revision-bound projection for a resumed
task. It preserves:

- the original objective;
- the declared scope and write authorization;
- the validated revision and implementation fingerprint;
- modified files from the engine validation;
- the active attempt, attempt count, repairs and review-correction budget;
- every required validation command;
- the latest failures and failed checks;
- unresolved review findings;
- human decisions and open interventions;
- evidence references.

Narration may be compacted through the existing reversible `history.compact`
archive, but the facts above are projected from durable records, not from a
summary. `require_current()` refuses a projection describing another revision.
The projection states on its face that it is not an authorization.

## 3. Before/after measurement

Two identical disposable projects, same request (`Fix the failing CSV export in
export.py`), same validation command, same six unchanged helper files in the
permitted scope. The only difference is `context_reduction`.

```text
profile     packet bytes    included sources    omitted sources
off             63,812              20                   0
adaptive        35,591              14                   6
```

| Measurement | Value | Classification |
|---|---|---|
| Packet bytes saved | **28,221** | Measured, file sizes |
| Packet reduction | **44.2%** | Derived arithmetic |
| Sources omitted | 6 optional unchanged scope files | Measured |
| Contract / request / mandatory methods retained | yes | Observed in both decisions |
| Token reduction | `UNKNOWN` | Not estimated |
| Provider prompt-cache effect | `UNKNOWN` | Not observed |
| Live task success after reduction | not run in this experiment | `UNKNOWN` |

The deterministic benchmark case
`intelligence.context-adaptive-reduction-is-measured` uses a smaller fixture and
asserts the same rule: the optional source is omitted, the required contract is
included, and bytes are measured.

## 4. Cache effectiveness

The shared deterministic run recorded:

| Metric | Value |
|---|---|
| Cache hits | 8 |
| Cache misses | 0 in the measured case |
| Invalidations | 4 |
| Stale-cache reuse | 0; the changed-source case re-derives |

These are **local deterministic source-hash reuses**, not provider-side prompt
cache reads. The existing
`adaptive-context.semantic-edit-invalidates-cache` case proves a changed source
is re-derived, and `context_cache_invalidates_after_source_modification` proves a
new mtime/size is a miss with an observable invalidation.

## 5. Safety properties tested

- Changed source invalidates the cached hash.
- A stale context decision is refused by revision and packet digest.
- Cache entries are isolated by run root (two projects do not share a cache).
- Adaptive reduction never omits the contract or a required source.
- A request that names the optional file keeps it.
- An empty request omits only optional scope files; the required contract remains.
- Continuation preserves the objective, scope, validation rows, latest failure
  and unresolved review finding.
- A continuation for a different revision is `STALE` and cannot be resumed.
- Forbidden context and untrusted skill text still cannot become authority.

## 6. Limitations

- The 44.2% figure is one Windows fixture with six large unchanged scope files.
  It demonstrates the mechanism; it is not a universal context reduction.
- Packet bytes are a proxy for request size, not provider tokens. No provider
  tokenizer or prompt-cache behavior was measured.
- The worker can still read the omitted file from disk. The saving is duplicated
  delivery, not access.
- Adaptive reduction is off by default. Enabling it does not change validation,
  review, gates or scope.
- No live task was run with adaptive reduction in this pass; the live samples
  used the default profile.

## 7. Enable and disable

```bash
# first packet of a task run
python scripts/ariadne.py task-start ... --context-reduction adaptive

# an existing run
python scripts/ariadne.py economics --context-reduction adaptive

# revert
python scripts/ariadne.py economics --context-reduction off
```

The efficiency configuration digest is recorded on the run state, so a report can
name the profile that produced it.
