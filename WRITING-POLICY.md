# WRITING POLICY

Writing requests use Ariadne's existing routing, workflow, evidence ladder and
independent-review boundary. This policy chooses a method inside that workflow;
it is not a second router or a new stage.

## Intent

After the router identifies writing as the object, record exactly one intent:

| Intent | Use when | Method | Review lens |
|---|---|---|---|
| CREATIVE | The work is meant to create an original literary or narrative artifact | Creative method | Creative editorial |
| ACADEMIC | The work answers an assignment or argues from sources | Argument and synthesis method | Academic editorial |
| SCIENTIFIC | The work explains, reports or interprets technical/scientific material | Evidence and uncertainty method | Scientific editorial |
| HUMAN-DRAFT TRANSFORMATION | The user supplies a draft and asks to improve, revise, edit or transform it | Transformation contract below | Transformation editorial |
| SOCIAL | The user requests posts, threads, distribution strategy or supplied social-result analysis | Existing social method only | Existing social checks |

If a request combines intents, choose the user's primary requested outcome and
record the secondary constraint. Do not silently turn a general writing request
into SOCIAL. SOCIAL keeps its own hooks, platform fit, voice evidence and
anti-generic rules in `skills/social-strategy.md` and `CONTENT-SYSTEM.md`.

## Shared method

1. Identify intent, audience, purpose, constraints and whether the input is a
   request for a draft or a transformation of supplied writing.
2. Choose the intent method below and record the evidence needed for its claims.
3. Draft or transform only within the stated purpose and constraints.
4. Send the result to an independent editorial review using the matching lens.
5. Revise the artifact and preserve the review findings that changed it.
6. Return the final artifact, unresolved uncertainty and the evidence boundary.

The reviewer must not rely on the drafting rationale as proof of quality. It
receives the artifact, intent, audience, purpose and stated success criteria,
then judges independently.

## Intent methods

### CREATIVE

Optimise for distinctive voice, concrete specificity, useful sensory detail,
character or subtext where relevant, rhythm, pacing, deliberate structure,
restraint and original imagery. Showing rather than telling is a choice tied to
the scene, not a mechanical rule. Do not force a plot shape, literary device or
voice onto every piece.

### ACADEMIC / ASSIGNMENT

Answer the actual prompt. Use a thesis or position when appropriate, then
claim -> reasoning -> evidence -> implication. Synthesize sources rather than
summarising them one by one. Use a counterargument when the question benefits
from one, and use clear signposting when it helps the reader. Preserve formal
clarity, accurate attribution and an argument-driven structure. Do not force a
five-paragraph essay, universal contractions rule or universal prohibition on
signposting.

### SCIENTIFIC / TECHNICAL

Optimise for precision, evidence fidelity, methodological clarity,
reproducibility, calibrated uncertainty, observation/inference separation,
correlation/causation discipline, exact metrics and appropriate structure.
IMRAD is available when the document and field call for it, not as a universal
format. State limitations and distinguish measured results from interpretation.

### HUMAN-DRAFT TRANSFORMATION

Distinguish "improve my writing" from "replace my writing with your own" before
editing. The intervention level is a user constraint, not an excuse to
homogenise the draft into polished generic prose.

**Inputs**

- original draft
- author's purpose and intended meaning
- requested degree of intervention
- audience
- explicit constraints, sources and submission requirements

**Process**

1. Identify what the author is actually saying.
2. Preserve substantive ideas and factual boundaries.
3. Identify intentional voice characteristics and unusual phrasing.
4. Identify structural, clarity, redundancy and correctness problems.
5. Improve only what the requested intervention requires.
6. Review for voice drift and unnecessary rewriting.
7. Compare the result against the original before returning it.

**Output record**

- final edited artifact
- change summary with representative examples
- reason for each material change
- intentional voice or unusual phrasing preserved
- uncertainty, ambiguity or unresolved author decision
- intervention level used and any places where it was exceeded

Context determines voice preservation. No fixed vocabulary-retention percentage
is required.

## General quality principles

These are quality judgements, not detector-evasion instructions:

- write from purpose, not a template;
- use concrete details when available;
- avoid unsupported generalities and inflated vocabulary;
- vary sentence rhythm naturally;
- use signposting only when it serves the reader;
- do not over-explain obvious conclusions;
- avoid generic introductions and conclusions;
- preserve meaningful specificity;
- do not make every paragraph symmetrical;
- do not manufacture personality, lived experience or quotations;
- do not fabricate evidence, sources, citations, page numbers, DOI numbers,
  statistics, results or source claims.

A conventional form is not automatically generic. The reviewer decides whether
it serves the purpose. This policy contains no phrase blacklist, detector
integration, humanizer, perplexity manipulation or detector-evasion heuristic.

## Evidence and citation discipline

Reuse Ariadne's Evidence Ladder and `RESEARCH-POLICY.md`; do not create a
writing-specific evidence store. When external sources are required, preserve
claim, date, source URL and confidence using the existing evidence rules. If
retrieval is unavailable, state the limitation and leave the claim unresolved.
Provider-neutral citation-format handling may be applied when requested, but
Ariadne never invents a reference or citation detail.

## Editorial review lens

The independent reviewer evaluates the artifact rather than defending the
method that produced it.

**General:** purpose, audience fit, clarity, specificity, structure, coherence,
prose quality, sentence rhythm, unnecessary padding, genericness and unsupported
claims.

**Creative:** voice, specificity, imagery, pacing, subtext, narrative judgment
and cliche avoidance.

**Academic:** prompt adherence, thesis/argument, reasoning, evidence, synthesis,
counterargument, academic register and citation integrity.

**Scientific:** claim discipline, evidence fidelity, uncertainty calibration,
methodological precision, reproducibility, causal discipline, terminology and
structure.

**Human-draft transformation:** voice preservation, idea preservation, structural
improvement, unnecessary rewriting, homogenisation and authorial intent.

Each finding names where it occurs, why it matters, severity and the smallest
useful revision. The reviewer records what it could not verify. A transformed
draft is compared with the original as evidence, not with an imagined ideal
voice.

### Review packet

The independent packet contains only the final artifact, the original draft
when applicable, recorded intent, audience, purpose, constraints and success
criteria. It excludes the drafting rationale and asks the reviewer to return
findings, uncertainty and a recommendation. The drafting session may not
author its own passing judgement.

## Benchmark

The focused regression fixture is [tests/writing-benchmark.md](tests/writing-benchmark.md).
It contains twelve high-value cases across the four general writing intents.
The benchmark catches routing, method, evidence, transformation and review
contract failures; it does not pretend to score literary quality automatically.
