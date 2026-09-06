# SKILL: social-strategy

**Trigger** — the user explicitly asks for launch strategy, social strategy, distribution help, post ideas, content planning, or analysis of supplied social results
**Owner** — Content strategist
**Inputs** — current project documents, approved thesis when one exists, implementation and rendered evidence when available, real assets, the user's social request, supplied voice examples, inspected current platform sources when behaviour matters, and user-provided performance evidence for learning
**Output** — conditional [`SOCIAL-STRATEGY.md`](../templates/SOCIAL-STRATEGY.md), conditional [`CONTENT-LEARNINGS.md`](../templates/CONTENT-LEARNINGS.md) after results exist, and hashed strategy/result/learning events in `.ariadne/creative-operations.json`

This optional method turns the actual project into a small distribution system.
It never publishes, authenticates, schedules, connects an account, buys reach,
changes a build gate, or promotes one project's results into Ariadne policy.
Use the existing reasoner boundary: Codex is verified; Claude remains externally
unverified until live execution exists.

## Strategy method

1. Confirm the user's explicit request. If the project originally skipped this
   optional method, record a `skill-activation` event with that request before
   invocation; never rewrite the earlier skipped history. Then read the richest
   project evidence available. Start with `PROJECT.md`; use `DESIGN.md`, `HANDOFF.md`, approved
   thesis, implementation, screenshots, recordings, references, assets and
   retrospective evidence when they exist. Do not reduce a finished project to
   its original brief.
2. Establish the project signal and objective before platform research:
   - what it is and why it exists;
   - what the content is trying to accomplish (objective: hiring proof, peer critique, adoption, technical insight, cultural signal);
   - the concrete maker decision or failure behind it;
   - what is unusual or useful to learn;
   - the strongest real moment and available visual evidence;
   - the audience most aligned with the project's actual purpose.
   Ask one small question only when the missing answer would change the story,
   audience, sensitive claim, voice treatment or final approval.
3. Explore two to four genuinely distinct creative angles before drafting:
   - each angle represents a different underlying story or mechanism (e.g. unexpected failure vs. technical constraint vs. counter-intuitive thesis vs. user surprise);
   - record core idea, project evidence, why the audience cares, emotional/curiosity driver, and risk for each;
   - select the strongest angle with an explicit qualitative rationale grounded in project evidence, not fake engagement scores.
4. Apply the "Reason to Exist" test to the selected direction:
   - answer why this deserves to become social content rather than remaining inside the project;
   - identify the specific value (surprising finding, demonstrated result, useful disagreement, important failure, or distinctive perspective);
   - reject generic announcements, superficial inspiration, or interchangeable AI takes.
5. Choose research depth: `minimal` for a bounded low-stakes question,
   `standard` for an ordinary launch, and `deep` for a high-value launch,
   uncertain audience or material multi-platform decision. Current format,
   feature, discovery, licence and analytics claims require current inspection.
6. Prefer official platform or creator guidance, then primary research,
   credible industry research and clearly labelled observed examples. Preserve
   the retrieval evidence. Each meaningful recommendation records
   `SOURCE -> FINDING -> DECISION`, access date, source quality and one of:
   `documented`, `observed`, `researched`, `inferred`, or `speculative`.
   Time-sensitive evidence older than 180 days is not current evidence.
7. Recommend one to three platforms and native formats as downstream consequences of the selected angle:
   - give each platform a specific fit with the angle and audience;
   - choose the communicative format (text post, carousel, short video, thread, case-study breakdown, process note) motivated by the idea and available visuals;
   - record relevant platforms deliberately not recommended and why;
   - distinguish evidence-backed timing from contextual recommendations or unknown evidence (never invent universal "best time" rules).
8. Define three to five content pillars only when the project naturally
   sustains them. Otherwise state why a smaller one-off sequence is better.
9. Produce three to six strong post concepts. Each needs an ID, platform,
   format, hook, hook score (1-5 with evidence-based rationale, minimum 4 required to draft without revision),
   complete draft, purpose, real visual asset or explicit `to-create`/`missing` status,
   CTA or `none`, evidence basis and falsifiable hypothesis. Use one changing variable per test.
10. Use existing visuals only when their paths can be hashed. If an image,
    recording, crop or diagram does not exist, say what must be created; never
    present it as available evidence.
11. Match the user's voice only when at least two supplied writing examples are
    recorded as evidence. With less evidence, label all copy `rough-draft` and
    use concrete project language without pretending to imitate the user.
12. Reject generic announcement structures, fake enthusiasm, corporate claims,
    invented achievements, engagement bait and promises of performance. Prefer
    an actual decision, number, failure, tension or observation from the work. Let
    writing structure emerge from the angle (narrative, post-mortem, argument, technical explanation, demonstration) rather than imposing one formula.
13. Fill `SOCIAL-STRATEGY.md`, record a contract-version 3 `social-strategy`
    event, then run `ariadne.py operations-check --require social`. A revised
    strategy gets a new ID and names its prior `revises` ID.

## Performance and learning method

1. Accept only results the user supplies through a screenshot, CSV, export or
   other preserved artifact. Record the platform, planned concept ID, date,
   available metrics and qualitative replies; absent metrics stay absent.
2. Record a `social-result` event. Provider-generated numbers, negative values,
   unsupported metric names and evidence-free results fail. A correction must
   preserve the old result and name it through `revises` with a reason.
3. Compare `PLAN -> RESULT -> INTERPRETATION -> NEXT TEST`. One result may only
   produce an `inconclusive` learning. A durable rule needs at least three
   distinct recorded results; otherwise keep the pattern under observation.
4. Update project-local `CONTENT-LEARNINGS.md`, record a `social-learning`
   event, and run `ariadne.py operations-check --require social-learning`.
   Change one variable in the next test and retain uncertainty explicitly.
5. In a fresh task, reload the project ledger and current strategy/learnings;
   do not reconstruct the result history from conversation memory.

## User-facing result

Keep the response understandable without marketing terminology:

- **What I recommend** — audience, selected platforms and exclusions.
- **Why** — the actual project story plus bounded evidence.
- **What I'd post** — the small platform-specific sequence and real visuals.
- **What I'd test** — hypotheses, measures and sustainable cadence.
- **What I need from you** — only missing voice evidence, sensitive-claim
  confirmation, final post approval, or user-supplied results.

## Stop conditions

- No explicit distribution or performance-analysis request: keep this method off.
- Project meaning is too thin to identify a truthful story: ask the smallest
  workflow-changing question instead of inventing one.
- A needed current source is inaccessible or stale: mark the limitation and
  omit, downgrade or reframe the affected recommendation.
- Account access, authentication, paid distribution, scheduling or publishing
  is requested: stop at the existing human authority boundary.
- Voice evidence is insufficient: produce rough drafts, not an imitation claim.
- Results are missing, contradictory or unsupported: preserve the gap or require
  an explicit correction; never manufacture a learning.
