# ADR-0211 — Adaptive context is a decision layer, never a compiler replacement

Status: accepted (AR-202)
Deciders: AR-202 implementation
Evidence: `src/ariadne_engine/context.py`, `scripts/prepare-stage.py` (`plan_sources`, `resolve_sources`, `prepare(context_plan=…)`), `03-ADAPTIVE-CONTEXT.md`

## Context
The AR-201 transport compiler already decides, correctly, what a packet must contain: canonical inputs, project inputs, conditional inputs, forbidden inputs, hash-stamped sections, a manifest and a packet digest. AR-202 needs context minimisation and caching, but rewriting the compiler would put the v1 packet contract at risk for a benefit that is not yet measured.

## Decision
Adaptive context is a layer *around* the compiler:

1. the transport exposes its own candidate list (`plan_sources`), the single implementation of the selection rules, read-only and without reading file content;
2. the engine records one `ContextDecision` per candidate with a machine-readable reason (included/omitted/required/unavailable/forbidden/cached/invalidated);
3. the transport receives a *plan* that may only **omit** a candidate it declared removable, or **reuse** the recorded hashes of a candidate it still delivers. A plan can never add a source, so a cache can never resurrect a forbidden source;
4. an omission of a required source is refused by the transport (`PacketError`), not silently ignored;
5. the recorded decision is reconciled with the manifest *after* preparation, so the stored record describes what the packet actually contains, not what the engine intended.

Caching is conservative: an entry is written only for a source that was actually delivered, and is reused only while the file's size and mtime identity, the stage, the policy version and the delivering packet's project revision all match. A cache never substitutes for source bytes: the source is still read and delivered verbatim.

## Alternatives considered
- **A second implementation of source selection in the engine.** Rejected: two implementations of one rule set is how context leaks become possible.
- **Summary-based context reduction.** Rejected for AR-202: lossy, and it would let a summary stand in for authoritative text (validation and review read exact text).
- **Omitting project inputs to save bytes.** Rejected: packet semantics are frozen; required sources stay required.
- **Removing a source from a packet after it is built.** Rejected: it would invalidate the packet digest and the evidence chain.

## Consequences
- Without a plan the packet is byte-identical to the AR-201 compiler's output; the transport self-test still passes unchanged, which is the compatibility proof.
- The measurable effects are source-count reduction for genuinely optional inputs, duplicate-content suppression, and avoided re-hashing on unchanged retries. Nothing else is claimed.
- Forbidden sources cannot be introduced by adaptive context by construction (there is no "include" in the plan).
