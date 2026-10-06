# AR-223: The Labelled Corpus

> **Several hundred reviewed decisions, in four splits, with the disagreements kept.**

A benchmark that flatters the thing it measures is worse than no benchmark, because it converts
an absence of evidence into a presence. Every property below exists to make flattering this
corpus harder.

## What is in it

```
corpus cases   406
corpus digest  7596ccfffd302861…

by family      FAILURE_CLASSIFICATION 112   REVIEW_ESCALATION 100
               EVIDENCE_RELEVANCE    102   ROUTE_FAMILY         92

by split       DEVELOPMENT 98   HELD_OUT 152   ADVERSARIAL 58   REAL_WORLD 98

difficulty     ORDINARY 270   SUBTLE 114   ADVERSARIAL 22

expected abstention   FAILURE_CLASSIFICATION 6, EVIDENCE_RELEVANCE 4, ROUTE_FAMILY 12

adjudicated labels   5
second-reviewed      33
```

Four families, and they are the four Ariadne actually asks about: `failure-classification`,
`review-escalation`, `evidence-relevance`, `route-family`. Nothing else was measured, because
measuring a family Ariadne never asks would be a benchmark for a system that does not exist.

## The splits, and what each is for

| Split | Rows | May be fitted on | May license anything |
| --- | --- | --- | --- |
| `DEVELOPMENT` | 98 | yes | no |
| `HELD_OUT` | 152 | no | yes |
| `REAL_WORLD` | 98 | no | yes |
| `ADVERSARIAL` | 58 | no | **never** |

`ADVERSARIAL` is excluded from licensing on purpose. It is deliberately unrepresentative, and a
corpus that let a stress set license production authority would be measuring its own
construction. Its findings are reported in
[Measured Intelligence](33-AR-223-MEASURED-INTELLIGENCE.md); it grants nothing.

`tuning_report` enforces this from the other side: asked which splits were tuned on, it returns
`clean: false` for anything containing `HELD_OUT`. A threshold fitted on held-out numbers is a
fitted number wearing a measured one's clothes.

## The leakage guards

Case ids are not enough. A corpus can have 406 unique ids and still be 200 questions, if two
rows differ only by a reworded failure description. So every row carries a
`projection_digest` — a canonical hash of its projection entries — and `leakage_problems`
reports any digest that appears in more than one split:

```
projection digest b165e315… appears in more than one split (DEVELOPMENT, HELD_OUT):
FC-HELD-001, INJECTED-001. Same question, two splits; a threshold fitted on one is fitted
on the other
```

This caught three genuine duplicates during authoring — route-family rows whose projections
were byte-identical across `DEVELOPMENT` and `REAL_WORLD` — and the fix was to make the rows
genuinely distinct rather than to renumber them.

`require_clean` **raises**. It does not warn. A leaky corpus produces a number that looks fine
and means nothing, and the only defence is refusing to produce it.

## Every label has a provenance

```text
reviewer        who wrote or checked it
round           which review pass
reviewed_at     when
source_kind     REVIEWED_FIXTURE | BOUNDARY_FIXTURE | ADVERSARIAL_FIXTURE | REAL_HISTORY
agreement       SINGLE_REVIEWER | SECOND_REVIEWER_AGREED | ADJUDICATED
```

`case()` refuses a row with no reviewer and refuses an agreement level that is not in the
declared vocabulary. Both refusals were added *because the adversarial suite found them
missing* — the corpus originally checked neither, so a mislabelled or unreviewable row could
have entered through the front door.

`case()` also refuses a label outside the family's declared answer space, read from the seeded
question itself rather than from a copy of the vocabulary that could drift.

## What each source kind claims

`REVIEWED_FIXTURE`
    A situation written for this corpus and judged against the family definition. Most rows.
    The reviewer determined the correct answer from the projection contract and the answer
    space, not from what any engine tends to say.
`BOUNDARY_FIXTURE`
    Written to sit exactly on the edge between two answers, usually where the honest answer is
    that the engine should abstain.
`ADVERSARIAL_FIXTURE`
    Written to break the engine, including the real 2.1 pathology where different inputs
    received the same classification at the same confidence.
`REAL_HISTORY`
    Drawn from outcomes Ariadne actually recorded: the documented AR-222 and AR-222D results in
    `docs/v2/2.2`, and the scenarios `scripts/real-world-shadow-eval.py` actually executes.

`REAL_WORLD` rows name their source in `source_record_id`. A `REAL_HISTORY` row is the only kind
that claims to describe something that happened, and the suite asserts that it stays a minority
of the corpus — a corpus where most rows claim real history is overstating what this
repository recorded.

## The disagreements, kept

Five rows were disputed in review. Both positions and the ruling are on the row, because the
ruling is the only part that would otherwise be invisible and the most likely part to be wrong.

```
FC-ADV-006  environment failure
  first review   an implementation failure, because the write target was chosen by the new code
  second review  an environment failure, because the permission denied came from the host
  adjudication   environment failure. Classifying by who chose the path would make the class
                 depend on intent the log cannot show, and the repair path for a host permission
                 problem is the same either way

FC-REAL-007  environment failure
  a missing package, read as context failure by one reviewer and environment failure by the other
  context failure is reserved for Ariadne failing to carry the state it needed; an absent
  dependency is a property of the host

RE-ADV-005   human_attention
  human_attention because the protected decision is the subject, enhanced_review because a
  protected decision was already made and only review remains
  human_attention. Once a protected decision is the thing under review, the review is itself a
  protected act

ER-ADV-009   IRRELEVANT
  the evidence describes a build that succeeded, which reads as SUPPORTS for a build
  requirement; the requirement as written is a visual layout requirement
  IRRELEVANT. Relevance is judged against the requirement as stated, not against a requirement
  the evidence would have satisfied, and no reviewer gets to move the goal

RF-ADV-009   implementation
  an unfamiliar framework migration read as recovery because it restores a broken capability,
  or as implementation because the work itself is a feature
  implementation. Recovery in this vocabulary means restoring the run to a working state after a
  failure, and no failure is recorded here
```

A corpus that erases disagreement is how a corpus with bad labels ends up used to condemn a
model. Five is a small number; it is the number that survived this review round, not the number
that existed.

## Cases the reviewers said should abstain

22 rows carry `expected_abstain`. These are the cases where the correct answer is "not
answerable", and they are what makes abstention quality measurable rather than assumed:

```text
abstention_precision   of the cases it declined, how many should have been declined
abstention_recall      of the cases that should have been declined, how many were
missed_abstentions     a false answer dressed as a right one
unwarranted_abstentions  a wasted cheap decision, and nothing else
```

The two mistakes are not symmetric, which is why both are counted and neither is the headline.
Missing a decline is a wrong answer. Declining something it could have handled is a cost.

## The rows themselves

Each is a literal tuple — `(case_id, label, projection, difficulty, expected_abstain)` — and
the label is the fourth thing that arrives, already written. Nothing derives one. Nothing
generates them. A generator would make "several hundred cases" trivially cheap and would make
it impossible to tell a real evaluation from a loop congratulating itself.

```python
("FC-REAL-010", "VALIDATION_FAILURE",
 {"failure": "HARNESS RESTORATION NOT PROVEN: the mutation harness exited before it could "
             "verify restoration"},
 "ORDINARY", False),

("FC-ADV-014", "UNKNOWN",
 {"failure": "the classification engine returned DIFFERENT FAILURES, SAME CLASS, SAME "
             "CONFIDENCE for every input in the batch, which is the shape of an engine that "
             "is not looking"},
 "ADVERSARIAL", True),
```

The second is the 2.1 pathology written down as a case, and `expected_abstain` is `True`
because an engine reporting one answer at one confidence for every input is not classifying
anything.

## Honest limits

The corpus is authored and reviewed. It is not scraped production traffic, because there is no
production traffic in this repository to scrape. `REAL_WORLD` is real documented history and real
executed scenarios, and it is 98 of 406 rows.

The engine under test is a naive-Bayes classifier over lexical features. Some families it
performs well on because the seeded weights encode the right rules for them; others it performs
badly on, and
[Measured Intelligence](33-AR-223-MEASURED-INTELLIGENCE.md) reports the bad numbers with the
same prominence as the good ones. A corpus that only contained the cases the engine happens to
handle would be a benchmark for the engine rather than for the milestone.

**Next:** [Measured Intelligence](33-AR-223-MEASURED-INTELLIGENCE.md) ·
[Results](34-AR-223-RESULTS.md)
