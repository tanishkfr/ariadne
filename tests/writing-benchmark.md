# WRITING BENCHMARK

Small architecture fixture. These cases test whether Ariadne selects and
records the right process; they do not mechanically determine literary quality.
Every case defines input, expected behavior, failure signals and pass criteria.

## Creative

### WB-01 Scene writing
- Input: A request for a 700-word scene between two siblings waiting outside a closed hospital room.
- Expected behavior: Select CREATIVE; use concrete detail, subtext, pacing and deliberate restraint.
- Failure signals: Assignment thesis, five-paragraph structure, invented biographical facts, or generic emotional summary.
- Pass criteria: Creative intent and method are recorded; review checks voice, imagery, pacing and subtext.

### WB-02 Dialogue
- Input: A request for tense dialogue where neither character says what they want.
- Expected behavior: Select CREATIVE; treat subtext and rhythm as scene-specific choices.
- Failure signals: Expository dialogue, symmetrical speeches, or forced sensory-detail checklist.
- Pass criteria: Creative review names subtext and narrative judgment as criteria.

### WB-03 Creative voice
- Input: A request for a first-person monologue in a clipped, observant voice supplied by the user.
- Expected behavior: Select CREATIVE; preserve the requested voice without manufacturing lived experience.
- Failure signals: Generic inspirational tone, voice imitation claim without evidence, or universal style rules.
- Pass criteria: Voice evidence and uncertainty are stated; review evaluates distinctiveness and specificity.

### WB-04 Human-draft polish
- Input: A rough 500-word personal essay with the instruction "improve clarity, keep my voice and show what changed."
- Expected behavior: Select HUMAN-DRAFT TRANSFORMATION; compare original and edit; preserve meaningful unusual phrasing.
- Failure signals: Silent rewrite, fixed vocabulary-retention promise, or no change record.
- Pass criteria: Output includes artifact, changes, reasons, preserved voice and unresolved choices.

## Academic

### WB-05 Argumentative assignment
- Input: A supplied prompt asking whether a school should adopt a four-day week, with two supplied sources.
- Expected behavior: Select ACADEMIC; answer the prompt with claim, reasoning, evidence and implication.
- Failure signals: Topic summary, fabricated source support, or forced five-paragraph essay.
- Pass criteria: Prompt adherence, argument structure and attribution are reviewed.

### WB-06 Source synthesis
- Input: Three supplied sources that disagree about remote-work productivity.
- Expected behavior: Select ACADEMIC; synthesize the disagreement and retain source boundaries.
- Failure signals: Source-by-source abstracts, averaged unsupported conclusion, or invented study details.
- Pass criteria: Synthesis, counterargument where useful and citation integrity are explicit.

### WB-07 Prompt adherence
- Input: A 1,200-word assignment prompt with audience, required question and word limit.
- Expected behavior: Select ACADEMIC; treat constraints as controlling and record any unresolved requirement.
- Failure signals: Answering a related question, generic introduction, or ignoring the word limit.
- Pass criteria: Review checks actual prompt, audience, structure and formal clarity.

### WB-08 Academic human-draft revision
- Input: A student's draft asking for argument clarity and grammar fixes while preserving their claims.
- Expected behavior: Select HUMAN-DRAFT TRANSFORMATION with academic review criteria.
- Failure signals: New claims or citations inserted without evidence, or author's position replaced.
- Pass criteria: Idea preservation, change rationale and evidence boundary are returned.

## Scientific / technical

### WB-09 Structured abstract
- Input: Results, methods and limitations for a small experiment, with no journal format specified.
- Expected behavior: Select SCIENTIFIC; choose an appropriate structure and state uncertainty.
- Failure signals: Forced IMRAD, causal claim beyond the design, or fabricated result.
- Pass criteria: Observation, inference, metrics and limitations remain distinct.

### WB-10 Technical explanation
- Input: A request to explain a caching failure to engineers and non-engineers using supplied logs.
- Expected behavior: Select SCIENTIFIC; calibrate terminology and preserve observed evidence.
- Failure signals: Unsupported root cause, inflated certainty, or one audience's vocabulary used for both.
- Pass criteria: Audience fit, methodological precision and evidence fidelity are reviewed.

### WB-11 Evidence-grounded discussion
- Input: A supplied paper excerpt and a request to discuss what it does and does not establish.
- Expected behavior: Select SCIENTIFIC; distinguish observation, inference and limitation.
- Failure signals: Invented DOI, page number, quotation, statistic or causal conclusion.
- Pass criteria: Citation details stay within the supplied evidence and uncertainty is visible.

### WB-12 Claim calibration
- Input: A draft says a correlated metric "proves" a feature caused retention growth.
- Expected behavior: Select SCIENTIFIC or HUMAN-DRAFT TRANSFORMATION based on the requested action; correct causal discipline.
- Failure signals: Silent voice replacement, retained unsupported causation, or invented experiment.
- Pass criteria: Review records the claim change, evidence boundary, remaining uncertainty and reason.
