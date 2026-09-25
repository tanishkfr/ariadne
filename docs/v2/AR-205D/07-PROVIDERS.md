# 07 — Providers

The decision provider interface is provider-neutral and declares what a provider
can actually do. No provider is special-cased anywhere in the engine.

## The interface

```
available()            -> (bool, reason)
capabilities()         -> the generic capability shape
confidence_kinds()     -> which confidence kinds the provider reports honestly
describe()             -> identity, availability, capabilities
answer(request)        -> one validated answer per question, or a failure
```

`answer` receives one batch request: the projected state, the independent
questions with their closed option sets, and the batch identity. It returns:

* one answer per question, keyed by question id;
* the provider, model and **concrete model version** it actually used;
* a provider request id where one exists;
* probability or confidence metadata *with its kind* — a bare number is not
  accepted as calibrated;
* usage figures where the provider exposes them, and nothing where it does not.

## Declared capabilities

```
primitives              BinaryDecision | ChoiceDecision | ScaleDecision |
                        MultiSelectDecision
batching                whether several independent questions may share one call
parallel_questions      the concurrency the provider declares
max_questions           the batch bound
max_options             the option-set bound
probabilities           whether probability output is real
confidence_kinds        NONE | SELF_REPORTED_CONFIDENCE | PROVIDER_PROBABILITY |
                        CALIBRATED_PROBABILITY
explicit_model_versions whether the provider can name a concrete version
state_limit_chars       the projected-state bound
usage_metadata          whether usage is reported
capability_names        provider-shaped capability labels
```

`providers.supports(...)` checks a concrete request against those declarations
before anything is sent: a primitive the provider does not declare, a batch over
its bound, an option set over its limit, a state over its character limit or a
probability requirement it cannot meet all produce a structured refusal instead
of a request the provider would mishandle.

Capabilities are registered in the engine's one capability registry
(`capabilities.declare`, family `decision`), never duplicated in provider code.
A declaration is evidence of `DECLARED` status and nothing more.

## The three shipped providers

* `DeterministicProvider` — scripted answers, confidence and failure for
  deterministic offline verification. It never pretends to be a live model.
* `UnavailableProvider` — the honest default. Nothing is configured, so the
  answer is `unavailable` and the caller falls back or escalates.
* `OptionalProviderAdapter` — an injection-only seam for a licensed or
  specialised service. It activates solely when an operator supplies an
  interface object and performs no network call, needs no credentials and never
  installs a dependency.

## Jev-shaped support

A Jev-style decision service maps naturally onto the generic interface through
`JevShapedAdapter`. The provider-side capability vocabulary is translated in one
place:

| Provider label | Generic meaning |
|---|---|
| `BINARY` | `BinaryDecision` |
| `CHOICE` | `ChoiceDecision` |
| `SCALE` | `ScaleDecision` |
| `MULTISELECT` | `MultiSelectDecision` |
| `PARALLEL_BATCH` | batching, with a declared parallel bound |
| `PROBABILITIES` | probability output with a probability confidence kind |
| `VERSIONED_MODEL` | explicit concrete model versions |

The adapter refuses to serve when the interface cannot report a concrete model
version, because an entry cached or recorded against a moving alias could be
served under a different model. It is exercised with offline fixtures only:
live service use is recorded as `NOT_EXECUTED`, no credential is required, and
no paid call is made. Jev is one possible provider, not Ariadne's identity — the
engine has no Jev dependency and the decision plane works without it.
