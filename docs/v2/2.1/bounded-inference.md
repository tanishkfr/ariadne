# Bounded inference

The answer-space contract is the whole of what the Decision Runtime agrees to do.
A bounded question is a question whose answer space is closed and declared before
the engine is asked, and the engine's job is to pick one label from that declared
set - or to refuse.

## The three supported primitives

`contracts.DECISION_PRIMITIVES` declares four. The runtime supports three:

| Primitive | Declared space | Engine answer |
|---|---|---|
| `BinaryDecision` | the declared pair `(positive, negative)` | one of the two |
| `ChoiceDecision` | an ordered `options` tuple | exactly one option |
| `ScaleDecision` | an ordered `scale` tuple of at least two steps | exactly one step |
| `MultiSelectDecision` | an option set plus `max_selections` | **refused** |

`contracts.RUNTIME_PRIMITIVE_MAPPINGS` records the Ariadne-primitive to runtime
task-type mapping. Today the engine reads only its *keys*, which become
`reference.SUPPORTED_PRIMITIVES`; the task-type labels are declared vocabulary
that no code consumes yet.

The engine declares the same set independently in
`session.REFERENCE_ENGINE_PRIMITIVES`, which is what it registers with the
capability registry:

```
batching                 True
parallel_questions       32
max_questions            32
max_options              32
probabilities            True
confidence_kinds         ("PROVIDER_PROBABILITY", "NONE")
explicit_model_versions  True
state_limit_chars        16000
usage_metadata           True
```

The manifest declares the engine's own limits separately
(`manifest.DEFAULT_CONTEXT_LIMITS`): `max_state_chars` 16000, `max_options` 32,
`max_questions_per_batch` 32, `max_question_chars` 2000. The tighter of the two
always applies; Ariadne's projection contract is the authority and these are only
what the implementation will not exceed.

## From a DecisionQuestion to an engine answer space

An Ariadne `DecisionQuestion` is a frozen dataclass whose `allowed` property is
the canonical answer space, derived per primitive. Before a question reaches the
engine it crosses the boundary in **record form**, and record form flattens
everything.

`DecisionQuestion.as_record()` emits, for every primitive:

```
question_id, instructions, primitive, options, scale, max_selections,
consequence, definition_version, evidence_digest, projection_contract, allowed
```

where `options` is `list(self.allowed)` and `allowed` is `list(self.allowed)` -
the same list, twice. So:

- a `ChoiceDecision` arrives with its options in both `allowed` and `options`,
  and `scale` empty;
- a `ScaleDecision` arrives with its scale in `allowed`, `options` *and* `scale`,
  because `allowed` for a scale *is* its scale;
- a `BinaryDecision` arrives with `(positive, negative)` in `allowed` and
  `options`, and no `positive`/`negative` keys at all.

`reference.answer_space()` is written specifically to survive that. It reads the
first populated encoding in this order:

1. `allowed`
2. `options`
3. `scale`
4. the `positive`/`negative` pair, if and only if the primitive is
   `BinaryDecision`

It has to read more than one field because a question produced by
`as_record()` and a question handed over as a bare primitive-specific dict do not
look the same, and a weight file fitted for one must keep matching the other. The
suite asserts that the answer space of all three primitives survives the record
round trip unchanged, and that the weight-book key is identical before and after
flattening.

Two degenerate cases are refused rather than scored: a primitive outside the
supported set, and a declared space of fewer than two answers. A one-option
question is not a bounded question, and the engine says so
(`EngineError`, "a bounded question needs at least two answers") instead of
returning that option with a confidence attached.

## Question identity: what a weight file is filed under

Weights are bound to a *question identity*, not to a label set in the abstract.
`reference.question_identity()` is a SHA-256 over the canonical JSON of exactly
five fields:

```
projection_contract   the contract name
question_id           the question id
primitive             the primitive
allowed               the ordered answer space
definition_version    the definition version
```

Two consequences worth stating precisely, because both are load-bearing:

- **Option order is part of the key.** An ordered answer space is positional;
  reordering it is a different question, and the fitted table no longer applies.
  The engine additionally refuses a fitted family whose label tuple does not equal
  the declared space, with `ANSWER_SPACE_MISMATCH`.
- **The instructions are not part of the key.** Re-wording a question does *not*
  change the weight-book key, so a table fitted to one wording still matches a
  reworded question. That is deliberate: the key identifies *which question
  family*, and wording is caught one level up. Rewording changes the **decision
  definition digest** (`profiles.decision_definition_digest`, which does include
  instructions), which is what invalidates a calibration profile and blocks an
  evaluation comparison. Two digests, two jobs; a reworded question keeps its
  weights and loses its calibration.

A question version bump changes the key, and therefore the identity of the family
the weights are filed under.

## The record form a call returns

`decide` / `decide_batch` return an object shaped like this:

```
provider, model, model_version, implementation_revision, runtime_version, device,
answers        keyed by "<state index>:<question id>"
abstained      keyed by the same slots, with a reason
failed_questions  the list of slots that failed rather than abstained
usage          states, questions, answer_slots, abstained, failed
```

Each answer slot carries `question_id`, `state_index`, `state_digest`, `answer`,
`valid`, `abstained`, `reason`, and, on an answer, `confidence`,
`confidence_kind` and the full `distribution`.

`confidence_kind` is `PROVIDER_PROBABILITY` on every answer the shipped engine
gives. It is never `CALIBRATED_PROBABILITY`, and the engine reports
`calibration_self_granted: false` in its status so that this is checkable rather
than assumed.

## The four seeded families

`seeds.seed_families()` builds the shipped weight book. Each family mirrors one
real Ariadne integration, so the answer space the engine is asked to fill is
exactly the space the integration already publishes, and the question identity
matches what the integration will actually ask:

| Question id | Projection contract | Answer space |
|---|---|---|
| `failure-class` | `failure-classification` | `DECISION_CLASSIFIABLE_FAILURE_CLASSES` - the seven classes a bounded decision may propose |
| `review-escalation` | `review-escalation` | `routine`, `independent_review`, `enhanced_review`, `human_attention` |
| `evidence-relevance` | `evidence-relevance` | `SUPPORTS`, `PARTIALLY_SUPPORTS`, `IRRELEVANT`, `CONTRADICTS`, `UNKNOWN` |
| `route-family` | `route-family` | `mechanical`, `implementation`, `design`, `research`, `recovery`, `unknown` |

Note what is *not* in that list. Authorization, revision, conflict and design
failures are deterministic facts - a refused gate, a changed revision, an illegal
state - and are never derived from a judgement. `REVIEW_FAILURE` and friends exist
in the wider failure taxonomy but are deliberately outside the classifiable set.

Each family is fitted from rule-derived examples written against the **real**
projection field names declared by `decisions.projections` - `failure`,
`validator_outcome`, `environment` for classification; `stakes`,
`affected_scope`, `verification_result`, `protected`, `review_findings` for
review; `requirement`, `evidence_claim`, `evidence_provenance`, `freshness` for
relevance; `task_kind`, `difficulty`, `stakes`, `available_capabilities`,
`required_capabilities` for route family. A seed keyed on invented field names
would produce features that never occur at inference time, which is exactly the
kind of plausible-but-wrong model this architecture exists to avoid.

The weight file's `source` field states the provenance exactly:
`ariadne deterministic decision tables (ar-205d decision-intelligence
answer-space vocabularies and projection contracts); rule-derived features, not a
trained corpus`.

## How the engine scores

`reference.score_question` is a multinomial naive-Bayes log-odds scorer over
feature tokens drawn from the projected state by `features_for`:

- every field contributes `f=<name>`, because `stakes=high` and `scope=high` are
  different evidence;
- a nested mapping contributes `f=<name>.<inner>` and `f=<name>.<inner>=<value>`;
- a list contributes `f=<name>=list<len>` plus up to sixteen `f=<name>~<item>`
  tokens;
- a string additionally contributes up to 512 `w=<name>:<word>` tokens;
- a float contributes its order of magnitude (`~1e3`), not its digits, because an
  exact-value feature would never recur.

Features are accumulated into the label prior, exponentiated with a
numerically-stable shift, and normalised to six decimal places. The argmax is the
answer. Unseen features are smoothed (`ADD_K = 1.0`), never zeroed, so an unseen
token lowers a probability instead of forbidding it.

A projection that expands past `MAX_FEATURES_PER_ITEM` (4000) is **refused**,
not truncated. A truncated score is a score about part of the state presented as
if it were the whole. `MAX_LABELS` is 32, matching the schema compiler's
`MAX_OPTIONS`.

## Why MultiSelectDecision is refused

A `MultiSelectDecision` asks for one or more of a declared option set, bounded by
`max_selections`. The engine scores exactly one closed label per question. Scoring
the options independently and reporting the top two would produce a confidence for
a *combination* that was never evaluated - the pair's joint likelihood is not the
product of the marginals, and nothing in the weight book was fitted on pairs.
Reporting that number would be a fabricated statistic with a real-looking value.

So the refusal happens at three levels, and each is load-bearing:

1. **The engine raises.** `score_question` raises `EngineError` containing
   `UNSUPPORTED_PRIMITIVE` for any primitive outside `SUPPORTED_PRIMITIVES`.
2. **The provider refuses the whole call.** `LocalBoundedProvider.answer` checks
   every question first and raises `DecisionProviderError` with
   `UNSUPPORTED_PRIMITIVE` naming the offending questions and the primitives it
   can answer. Refusing the call is safer than sending a question the engine
   cannot represent and reading its error as an answer - a partial answer set
   invites the caller to treat the rest as ordinary failures of a different kind.
3. **Status says so up front.** `status["unsupported_primitives"]` lists every
   `DECISION_PRIMITIVES` member the runtime does not declare, which for the
   reference engine is exactly `("MultiSelectDecision",)`. An absent runtime
   reports all four, honestly.

From the Decision Plane's point of view this is an ordinary unavailable-provider
condition, so Ariadne's normal fallback and escalation ladder take it. Nothing
about the path is special-cased for this primitive.

## Narrowing before the question

Two modules exist so that a question stays inside the budget the engine agreed to.

`shortlist.py` narrows a large candidate set before it becomes a question.
`DEFAULT_KEEP` is 12, `MAX_CANDIDATES` is 5000 (a larger set is refused as an
unbounded enumeration, not ranked), and there are three strategies in preference
order: `declared` (a named match key, fully deterministic), `lexical` (stable
token overlap with a declared-order tie-break, still no model), and `embedding`,
which is **refused** unless the caller supplies the embedding function explicitly
- because otherwise the result depends on a model the projection never named.
Every shortlist records what went in, what survived, what was dropped, which
strategy ran, and a digest of the input, because a shortlist that silently
discards the correct candidate is otherwise indistinguishable from one that found
it.

`schema.py` compiles a safe subset of JSON Schema into Ariadne primitives:
an `enum` becomes a `ChoiceDecision` (or a `BinaryDecision` when every value is
boolean), a `boolean` becomes a `BinaryDecision`, and an `integer` with an integer
`minimum` and `maximum` becomes a `ScaleDecision` of at most `MAX_SCORE_LEVELS`
(10) steps. Everything else is refused with a reason: free strings (no closed
answer space), arrays and nested objects (the runtime scores one closed label per
question), `$ref` and recursion (the compiler is not a resolver), an unbounded
number (declare a range), more than `MAX_PROPERTIES` (32) fields, or more than
`MAX_OPTIONS` (32) values.

The direction of dependency is the point: an Ariadne contract compiles *into*
Ariadne `DecisionQuestion` objects, and those are what the runtime is handed. The
runtime's own question format never appears in Ariadne's API, and swapping the
engine cannot change what Ariadne considers a well-formed bounded question.
