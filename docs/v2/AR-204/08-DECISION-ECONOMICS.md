# AR-204 — Decision Economics

Code before judgment, judgment before generation — now with a price comparison
attached to it.

## 1. The three layers, side by side

`economics.decision_layer_cost` reports deterministic code, bounded decisions and
generative inference in one structure:

| Layer | What counts | Cost basis |
| --- | --- | --- |
| deterministic | provider calls: zero, by construction | measured: nothing was called |
| bounded | batches, their questions and their measured usage | measured only when a provider reported usage |
| generative | the usage the caller supplies for a generative comparison | measured only when supplied |

A layer with no measurement reports `UNKNOWN`. The comparison never assumes that a
bounded decision is cheaper than a generative call, because that assumption is
exactly the kind of unmeasured claim the milestone forbids.

## 2. A batch is one request over one state

AR-203's Decision Plane already evaluates independent questions against a single
projected state. AR-204 adds the accounting:

* `state_bytes` from the recorded projection length, so the shared-state cost is
  visible per batch;
* `request_count` derived from whether a provider was actually consulted;
* usage attribution to the batch's task, taken from the provider response the
  batch already stores;
* per-question results, so an answer's provenance is not flattened into a batch
  total.

The benchmark asserts that a two-question batch uses one request, shares one state
digest and records no dependency problem, and that the same batch is attributed to
the right task and unmeasured usage stays unmeasured.

## 3. Dependency is refused, not hidden

A batch whose questions depend on each other would hide a sequencing error behind
a single call, so `economics.batch_dependency_problems` refuses any declared
dependency inside one batch, including a self-dependency. Invariance 50 gets a
direct test and a mutation: with the guard disabled, the benchmark case fails.

`economics.plan_batches` turns a dependency map into sequential steps: questions
with no unresolved dependency share a step, everything else waits for a later one,
and a cycle is refused rather than silently ordered.

## 4. Speculative bounded questions

The brief allows evaluating several independent potential decisions over one
shared state and discarding the unused answers. This is a provider-capability
question, not an engine one: it is economical only where a provider prices a
multi-question call below the sum of single-question calls and reports the usage to
prove it. The engine therefore prepares the plan and does not execute one:

* `plan_batches` returns the steps a speculative evaluation would use;
* the capability comparison is `decision_layer_cost`, which needs measured usage
  from both shapes before it can say anything;
* a fixture provider may be used to test correctness of the shape, and it is — the
  deterministic provider answers a scripted batch in the suite;
* against a real provider this is recorded as `NOT_EXECUTED` in
  [10-EXPERIMENTS.md](10-EXPERIMENTS.md), because no authorized provider was
  called.

## 5. Provider neutrality

Nothing in the decision economics requires a particular provider. The provider
contract in `decisions/providers.py` is the only interface, the deterministic
provider is the reference implementation, and an optional adapter contract exists
for a provider that offers bounded primitives with usage records. A provider that
reports usage gets measured; one that does not stays `UNKNOWN`. The engine never
infers a shape from a model name.

## 6. What would justify a bounded decision

The rule the AR-203 milestone installed still governs: a deterministic function
answers exactly, a bounded decision answers within a declared space, and only a
generative call creates. AR-204 adds the economic test — a bounded decision is
worth its request when the alternative is a generative call that would have to
produce the same judgement plus the material around it. That test is decided from
measured usage, and until both shapes are measured the honest answer is that the
comparison is open.
