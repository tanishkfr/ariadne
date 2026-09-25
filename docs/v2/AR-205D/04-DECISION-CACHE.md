# 04 — Decision cache

`ariadne_engine.decisions.cache` reuses a bounded decision only while everything
that produced it is still the same. The cache key binds all of it:

```
key = H( question definition digest | projection digest | provider |
         concrete model version | policy version )
```

Keying on task text or a bare question id is refused by construction. A concrete
model version is mandatory, and a moving alias such as `jev-latest` is rejected
outright: an entry stored against an alias could be served under a model the
original decision never saw.

## What a cache entry holds

```
cache_id, key, question_id, definition_version, definition_digest,
primitive, options, state_digest, provider, model, model_version,
policy_version, source_decision_id, answer, answers, answer_valid,
confidence, confidence_kind, distribution, fingerprints, freshness,
reason, superseded_by, expires_at, authorization_effect, recorded_at
```

Only a validated, answered decision is cacheable, and only with a concrete model
version. The entry cites the decision that produced it — it never becomes a
decision of its own.

## Reuse preserves provenance

A cache hit does not return a stale record unchanged. `materialise` writes a new
decision record that:

* cites the original decision and the cache entry;
* copies the original confidence and confidence kind exactly — reuse never raises
  confidence, because agreement with an earlier call is not new evidence;
* re-runs the *current* policy against the *current* consequence class and
  verification level, so an answer accepted for a low-stakes judgement can still
  be refused when it is reused under weaker evidence;
* records `authorization_effect: none`, always.

A cached decision therefore does not become more trustworthy because it was
reused, and the batch record that documents the reuse states
`provider_available: false` with the reason "served from the decision cache; no
provider call was made", so the economics never count a reuse as a model call.

## Invalidation

Reuse stops when any binding changes. The structured miss reasons are:

| Reason | What changed |
|---|---|
| `NO_ENTRY` | Nothing has been cached for this question. |
| `QUESTION_DEFINITION_CHANGED` | The question id stayed but its definition, options or version moved. |
| `STATE_CHANGED` | The projected evidence digest differs. |
| `PROVIDER_CHANGED` | A different provider identity is configured. |
| `MODEL_VERSION_CHANGED` | The concrete model version differs. |
| `POLICY_VERSION_CHANGED` | The policy under which it was accepted is not the current one. |
| `FINGERPRINT_CHANGED` | A stored dependency fingerprint no longer matches. |
| `EXPIRED` | The entry passed its declared TTL. |
| `REVOKED` | An operator or engine explicitly revoked it. |
| `SUPERSEDED` | A newer entry replaced it. |

Invalidation is content-driven rather than global: a change in irrelevant run
state does not touch the cache, while a changed projection, capability state,
model version, question definition or policy version does. `invalidate` requires
a recorded reason; `expire` marks time-bound entries stale rather than deleting
them, because deletion would destroy the evidence that a decision was once made.
