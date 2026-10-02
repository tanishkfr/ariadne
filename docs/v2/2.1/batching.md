# Batching

One projected state, many independent questions, one inference. This is the
reason the transport exists at all.

## The unit of work

The Decision Runtime's contract is not "answer a question". It is:

> take one projected state, take a set of questions the planner has already
> proved independent, and produce one bounded inference over the cross product.

`decide(state, questions)` is the single-state case and always uses state index
`0`. `decide_batch(states, questions)` is the general case. Both are one call
over the pipe, one feature extraction per state, one scoring pass. Nothing is
issued per question.

This is not an optimisation. Three questions over one projection issued as three
calls would mean three pipe round-trips, three copies of the same projected state
crossing the boundary, and three chances for one of them to time out and be
recorded as a separate failure. One call means the questions share one unit of
work and one unit of failure.

## The answer-slot naming

Results are keyed, never positional:

```
"<state index>:<question id>"
```

So `decide` over one state returns keys like:

```
0:failure-class
0:review-escalation
0:evidence-relevance
```

and `decide_batch` over three states returns nine keys, `0:` through `2:`. The
key is a *slot*, not an ordering guarantee: two identical states in one batch
produce identical answers, and a caller reads by key rather than by position.

Three fields make the mapping exact rather than merely plausible:

- **The key carries both coordinates.** A question id alone is ambiguous across
  states; a state index alone is ambiguous across questions.
- **Each slot carries `state_digest`.** The digest of the state it belongs to,
  taken from the request, so a caller can confirm which projected state produced
  which answer without relying on the index.
- **`usage.answer_slots` reports the size.** `states * questions`, recorded by the
  engine, not inferred by the caller.

`failed_questions` lists the slots that failed; `abstained` maps the same slot
keys to their reasons. A question the engine could not answer is reported in one
of those two places and is never filled from a neighbour.

## Usage accounting

```
usage.states         how many projected states went in
usage.questions      how many questions went in
usage.answer_slots   states * questions
usage.abstained      how many slots abstained, with a reason
usage.failed         how many slots failed
```

The suite asserts this block rather than inferring call counts: three questions
over one state cost one inference unit, and a three-state by three-question batch
reports `answer_slots == 9`.

`observe_many` reports `inference_calls: 1` alongside the number of records it
stored, for the same reason - the useful fact about a batch is how much work it
was, not how many records it produced.

## Empty calls are refused

`decide_batch` raises `EngineError` for zero states ("a decide call needs at
least one state") and for zero questions ("a decide call needs at least one
question"). An empty call answered with an empty result would be indistinguishable
from a call that ran and abstained on everything, and those two facts demand
different responses.

## Missing answers are reported, not filled

A question whose family has no weights in this installation comes back as:

```
{"answer": null, "valid": false, "abstained": true, "reason": "NO_LOCAL_MODEL"}
```

while its sibling in the same call is answered normally. The refusal is scoped to
the one slot. This is the property that makes batching safe to use aggressively:
one unsupported question in a batch of three costs you that question, not the
call.

## Why dependent questions stay staged

The runtime can only collapse questions that are already independent. It does not
decide independence itself, and it must not: two questions over the same state
where the second's answer space depends on the first's answer cannot be answered
in one inference, and a runtime that collapsed them would be answering a question
nobody asked.

**The AR-205D planner owns staging.** `planner.plan_steps(questions,
depends_on=...)` groups independent questions into steps and proves each step's
independence with the AR-204 dependency check. A dependent question is staged into
a *later* step rather than refused - the protection applies to each step, which is
what a single provider call would otherwise hide - and a dependency cycle is
refused outright, because staging cannot resolve one.

Inside a step, `planner.group_step(step_questions, projections)` produces one
group per shared projection contract. Two rules matter here:

- a question with **no declared projection contract** is refused, not grouped;
  bounded judgement needs the smallest defensible state, declared;
- a question whose declared contract has **no projected state** is refused too.

The result of that grouping is what the runtime is handed, and it is why a single
`decide` call over one projection is the only shape the runtime sees in
production: the plane has already established that one projection answers this set
of questions and no others.

`LocalBoundedProvider.answer` is the one provider call over that grouped step. It
refuses the whole call when any question uses an unsupported primitive, and it
reads results back by the `0:<question id>` slot, which is correct precisely
because the provider path is single-state.

## Determinism under repetition

`SubprocessTransport` and `InProcessTransport` both serialise calls behind one
lock. A sidecar is single-threaded, and letting two calls interleave inside one
engine would make batch results order-dependent - which would, among other
things, break the dataset digest that makes two evaluation runs comparable.

The same property is asserted at the level that matters: identical states in one
batch produce identical answers, and the in-process and subprocess routes agree
exactly on the same question.

## Why the projection, not the question, is the shared cost

`decide_batch` over *many* states and *many* questions is the general shape, and
it costs one feature extraction per state, not per question-state pair. The
features come from `state["entries"]` (or the state itself, when a caller passes
entries directly), so a projection of N fields is tokenised once and scored
against every question's weight table.

That is what makes the shape worth having for Ariadne's own integrations: the
four families in `seeds.py` are asked about the same run, and the projected state
each of them needs is small. The engine's declared `state_limit_chars` is 16000,
and the manifest's `max_questions_per_batch` is 32 - both bounds, not suggestions.

## What batching does not do

- It does not retry. A failed slot is recorded; re-running is the caller's
  decision, with its own cost.
- It does not partially succeed quietly. `failed_questions` and `abstained` are
  both reported, so a caller can tell "answered", "abstained" and "failed" apart
  - and the provider adapter converts an abstention into `answer: None`,
  `confidence_kind: "NONE"` and an entry in `failed_questions`, so an abstention
  is never mistaken for a weak answer.
- It does not merge or de-duplicate questions. Two questions sharing an id produce
  two answers under the same key, so the second write replaces the first at the
  runtime layer. That is a caller bug, and it is caught one level up rather than
  here: `contracts.decision_batch_problems` (in `ariadne_engine.contracts`)
  refuses a recorded decision batch that
  repeats a question id, so the collapse never reaches the run state as a
  legitimate batch.
