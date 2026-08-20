# CONTENT SYSTEM

A system for writing posts that sound like a person, for X and LinkedIn, that gets better because it looks at what actually happened.

**The hard constraint:** nothing publishes automatically. Ever. G5 is per-post, every post, no standing approval. See [AUTONOMY-POLICY.md](AUTONOMY-POLICY.md).

Owned by the Content strategist ([AGENT-ROLES.md](AGENT-ROLES.md) role 12). Skill: [skills/content-strategy.md](skills/content-strategy.md). Mode: [modes/content-system.md](modes/content-system.md).

---

## 1. Why AI writing is detectable

Not because of vocabulary. Because of **structure**. LLM-written posts share a shape:

- A rhetorical question opener.
- Three parallel points, each the same length.
- The em-dash-and-reversal construction, repeatedly.
- A "here's the thing" pivot.
- A tidy closing lesson that resolves the tension.
- Confident generalisation with no specific instance behind it.

Human writing is lumpier. One point gets four sentences, the next gets three words. It goes on a tangent. It admits it does not know. It names a Tuesday, a number, a person, a specific failure.

**The rule that does the most work: a post must contain at least one thing only you could have written.** A specific number, a real conversation, a mistake with a date, a thing you were wrong about. Without that anchor, it is a generic take, and generic takes read as AI whether or not they are.

---

## 2. Voice discovery

Done once, refined quarterly. Output: `voice-profile.md`, kept in the content project, **not** in the Builder OS ([PRIVACY-POLICY.md](PRIVACY-POLICY.md)).

Collect 10-20 things you have actually written — DMs, commit messages, notes, old posts — and extract:

| Dimension | Question |
|---|---|
| Sentence rhythm | Long and winding, or short and clipped? Mixed how? |
| Formality | Contractions? Slang? Profanity? |
| Stance | Do you assert, hedge, or ask? |
| Humour | Dry, absurd, self-deprecating, none? |
| Structure | Do you open with the conclusion or build to it? |
| Vocabulary | Words you actually use. Words you would never use. |
| Tells | Your habitual constructions — the things that make it yours |

Also record the **anti-voice**: constructions you find embarrassing. This list is more useful than the voice list, because it is easier to enforce. Minimum ten entries. Start with: "Let that sink in", "Here's the thing", "Unpopular opinion", "I'll say it louder", "Game changer", "This changes everything", "Read that again", any post that is a single word per line.

---

## 3. Content pillars

Three to five. Each is a subject you can post on for a year without repeating yourself.

Each pillar records: what it is, why you specifically can speak to it, what you bring that the standard take does not, and roughly what proportion of output it gets.

Good pillars come from the intersection of what you make, what you notice, and what you have been wrong about. A pillar you cannot supply a specific personal instance for is a topic, not a pillar — drop it.

Recommended split: roughly 60% pillars you have real depth in, 30% adjacent, 10% experiments.

---

## 4. Ideation

Ideas come from work, not from a content calendar. Sources, in order of quality:

1. **Something that happened while building.** A bug, a decision, a rejected approach, a retrospective finding. `RETROSPECTIVE.md` files are the best idea source you have.
2. **Something you changed your mind about.** Highest-engagement category and the hardest to fake.
3. **A specific number.** Measured, not estimated.
4. **A thing everyone says that is wrong**, where you can show why with a real case.
5. **A process made visible.** Not "how to design" — how *you* did this one, including what failed.

Keep a running idea list with the source instance attached. An idea without a specific instance is not ready.

**Never** generate ideas by asking a model "what should I post about". That produces the statistical centre of the discourse, which is where every generic post already lives.

---

## 5. Human-sounding writing rules

**Structure**

- Vary paragraph length dramatically. One sentence. Then five.
- Do not resolve everything. It is fine to end on an open question you actually have.
- Bury one idea in the middle with no signposting. Real writing has texture.
- Do not use three parallel examples. Use one, in detail, or two of unequal weight.

**Language**

- Specific over general: "a 340KB font file" beats "a large font file".
- Name real things: tools, versions, numbers, days.
- Contractions, always.
- Cut every intensifier that is not load-bearing: very, really, incredibly, absolutely.
- No em-dash-reversal as a tic. Once per post at most.
- Do not open with a rhetorical question.
- Do not close with a lesson. Trust the reader.

**Stance**

- Say the thing plainly. If it is a strong opinion, own it without the "unpopular opinion" framing.
- Admit uncertainty where it exists. "I'm not sure this generalises" is a credibility signal.
- Never claim experience you do not have. Never invent a client, a result, or a metric. This is not a style rule — it is [AUTONOMY-POLICY.md](AUTONOMY-POLICY.md) Red tier.

**The read-aloud test.** Read it out loud. Anywhere you would not say it that way to a person, rewrite it. This one test catches most of it.

---

## 6. Hook quality

The first line decides whether anything else is read. Scored 1-5 before drafting the rest:

| Score | Hook |
|---|---|
| 1 | Rhetorical question, or a truism |
| 2 | Clear but generic — "I've been thinking about design systems" |
| 3 | Specific but not compelling |
| 4 | Specific + tension. A number, a contradiction, a stake |
| 5 | Specific + tension + only-you. Could not have been written by anyone else |

**Below 4 does not get drafted.** Rewrite the hook or drop the post. The most common failure is a 5-quality idea with a 2-quality hook.

Hooks that work: a specific number that sounds wrong; a thing you were wrong about; a concrete moment ("A client asked me to remove the one part I liked"); a flat contradiction of a common belief, with evidence ready.

Hooks that do not: "Let's talk about X." "X is more important than you think." "Most people get X wrong." Anything a hundred accounts posted this week.

---

## 7. Platform adaptation

Same idea, different form. **Never cross-post the same text.** Character limits and formatting conventions change; verify current specifics per [RESEARCH-POLICY.md](RESEARCH-POLICY.md) rather than trusting these notes to stay accurate.

### X / Twitter

- Compression is the craft. Cut until removing another word breaks it.
- Single post beats a thread unless the idea genuinely has sequential parts. Threads that should have been one post are obvious.
- If threading: each post must stand alone and earn the next. No "1/12" as a promise of value.
- No engagement bait, no "follow for more", no reply-guy framing.
- Images and short video carry well; a screenshot of the actual thing beats describing it.

### LinkedIn

- More room, and readers expect context. This is not permission to inflate.
- The first two lines are all that shows before the fold. That is your hook budget.
- Line breaks aid scanning — but one-line-per-sentence for a whole post is the platform's most recognisable slop pattern. Use real paragraphs with occasional breaks.
- Professional does not mean stiff. The best-performing LinkedIn writing is specific and slightly more careful than X, not more formal.
- Avoid: the humblebrag-lesson structure, fake vulnerability, "I'm humbled to announce", anything ending in a question aimed at farming comments.

### Adaptation method

Write the **idea** first, platform-neutral: the claim, the specific instance, the tension. Then write each platform version from the idea, not from the other version. Adaptations of adaptations lose the point.

---

## 8. Originality checks

Before G5, every post passes all five:

1. **Only-you test** — is there one thing here nobody else could have written? If no, do not post.
2. **Anti-voice sweep** — scan against the section 2 list. Any hit, rewrite.
3. **Structure check** — three parallel points? Tidy closing lesson? Rhetorical opener? Rewrite.
4. **Prior-art check** — has this exact take been everywhere this month? If so, either add the thing that makes it yours, or drop it.
5. **Read-aloud** — section 5.

The Content strategist **must flag its own output** when it detects these patterns. A draft that arrives with "the close on this reads AI-generated, here's an alternative" is doing its job.

---

## 9. Publishing — G5

```
G5: PUBLISH REQUEST
Platform:   <X | LinkedIn>
Pillar:     <which>
Hook score: <n>/5
Only-you:   <the specific thing only you could write>
Checks:     <5/5 passed, or which failed and why posting anyway>
Draft:      <exact text>
Experiment: <what this is testing, or "none">
```

You copy the text and post it yourself. The system never touches an account, never schedules, never bulk-posts, never connects via API. This is not a limitation to work around — it is the design. Connecting a publishing integration is an Amber action requiring explicit approval, and the default answer is no.

---

## 10. Analytics

**You** export or paste the numbers. The system has no account access.

Per post, record: date, platform, pillar, hook score, format, impressions, engagements, profile visits, follows, and any qualitative signal — who replied, what they said, whether anyone useful saw it. Weekly is enough; per-post-per-day is noise.

**Qualitative beats quantitative here.** One reply from someone whose work you respect is worth more than 5,000 impressions. Record it, because impression counts will not.

Caveats to write down and keep writing down: small samples, platform algorithm changes, timing effects, and the fact that a post's performance is mostly determined by things you do not control. Do not build a rule from one post.

---

## 11. Weekly review

Twenty minutes. Output: an appended entry in [`CONTENT-LEARNINGS.md`](templates/CONTENT-LEARNINGS.md).

1. What went out, and how did each do?
2. Best and worst — and is the difference explainable, or noise?
3. Did any hypothesis get supported or contradicted?
4. What did people actually respond to, in replies rather than counts?
5. One change for next week. One.

**Only promote a pattern to a rule after it holds three times.** Two data points is a coincidence. This is the discipline that separates a learning system from a superstition generator.

---

## 12. Experiments

One at a time. Change one variable.

```
EXPERIMENT
Hypothesis: <specific and falsifiable>
Variable:   <the single thing changing>
Posts:      <how many, over what period>
Measure:    <what result would support it, what would refute it>
Result:     <filled in after; "inconclusive" is a valid outcome>
```

Good experiments: hook style, post length, threading vs single, posting time, first-person vs instructional framing, image vs text.

Bad experiments: changing three things at once, anything measured on a single post, anything where the honest answer is "the algorithm decided".

Inconclusive is the most common correct result. Record it as such rather than forcing a conclusion.

---

## 13. The learning loop

```
Pillars -> Idea (from real work) -> Hook (score >=4) -> Draft (voice rules)
   -> Originality checks -> G5 -> You post -> Analytics -> Weekly review
   -> CONTENT-LEARNINGS.md -> updates pillars, voice, hooks, experiments
```

The loop closes at `CONTENT-LEARNINGS.md`. If a weekly review does not change that file, the loop is open and the system is not learning — it is just producing.

**Quarterly:** re-read the whole learnings file. Which rules held? Which were noise? Rewrite the voice profile if your actual voice has moved. Prune rules built on two data points that never got a third.
