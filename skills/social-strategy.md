# SKILL: social-strategy

**Trigger** — the user explicitly asks for launch strategy, social strategy, distribution help, post ideas, content planning, or analysis of supplied social results
**Owner** — Content strategist
**Inputs** — current project documents, approved thesis when one exists, implementation and rendered evidence when available, real assets, the user's social request, supplied voice examples, inspected current platform sources when behaviour matters, and user-provided performance evidence for learning
**Output** — conditional [`SOCIAL-STRATEGY.md`](../templates/SOCIAL-STRATEGY.md), conditional [`CONTENT-LEARNINGS.md`](../templates/CONTENT-LEARNINGS.md) after results exist, and hashed strategy/result/learning events in `.builderos/creative-operations.json`

This optional method turns the actual project into a small distribution system.
It never publishes, authenticates, schedules, connects an account, buys reach,
changes a build gate, or promotes one project's results into Builder OS policy.
Use the existing reasoner boundary: Codex is verified; Claude remains externally
unverified until live execution exists.

## Strategy method

1. Confirm the user's explicit request, then read the richest project evidence
   available. Start with `PROJECT.md`; use `DESIGN.md`, `HANDOFF.md`, approved
   thesis, implementation, screenshots, recordings, references, assets and
   retrospective evidence when they exist. Do not reduce a finished project to
   its original brief.
2. Establish the project signal before platform research:
   - what it is and why it exists;
   - the concrete maker decision or failure behind it;
   - what is unusual or useful to learn;
   - the strongest real moment and available visual evidence;
   - the audience most aligned with the project's actual purpose.
   Ask one small question only when the missing answer would change the story,
   audience, sensitive claim, voice treatment or final approval.
3. Choose research depth: `minimal` for a bounded low-stakes question,
   `standard` for an ordinary launch, and `deep` for a high-value launch,
   uncertain audience or material multi-platform decision. Current format,
   feature, discovery, licence and analytics claims require current inspection.
4. Prefer official platform or creator guidance, then primary research,
   credible industry research and clearly labelled observed examples. Preserve
   the retrieval evidence. Each meaningful recommendation records
   `SOURCE -> FINDING -> DECISION`, access date, source quality and one of:
   `documented`, `observed`, `researched`, `inferred`, or `speculative`.
   Time-sensitive evidence older than 180 days is not current evidence.
5. Recommend one to three platforms. Give each a project-specific fit, native
   treatment and test. Record relevant platforms deliberately not recommended
   and why. Never spread one generic draft across every platform.
6. Define three to five content pillars only when the project naturally
   sustains them. Otherwise state why a smaller one-off sequence is better.
7. Produce three to six strong post concepts. Each needs an ID, platform,
   format, hook, complete draft, purpose, real visual asset or explicit
   `to-create`/`missing` status, CTA or `none`, evidence basis and falsifiable
   hypothesis. Use one changing variable per test.
8. Use existing visuals only when their paths can be hashed. If an image,
   recording, crop or diagram does not exist, say what must be created; never
   present it as available evidence.
9. Match the user's voice only when at least two supplied writing examples are
   recorded as evidence. With less evidence, label all copy `rough-draft` and
   use concrete project language without pretending to imitate the user.
10. Reject generic announcement structures, fake enthusiasm, corporate claims,
    invented achievements, engagement bait and promises of performance. Prefer
    an actual decision, number, failure, tension or observation from the work.
11. Fill `SOCIAL-STRATEGY.md`, record a contract-version 2 `social-strategy`
    event, then run `builderos.py operations-check --require social`. A revised
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
   event, and run `builderos.py operations-check --require social-learning`.
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
