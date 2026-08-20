# PROMPT: Content system

**Paste into:** your reasoning tool. Two prompts here — **setup** (once) and **drafting** (per post).

System: [CONTENT-SYSTEM.md](../CONTENT-SYSTEM.md). **Nothing publishes automatically. Ever.**

---

## Prompt 1 — Setup (run once)

```
You are the Content strategist role in my Builder OS. We are setting up my
content system for X and LinkedIn. This is setup, not drafting — do not write
any posts yet.

STEP 1 — VOICE
I will paste 10-20 things I have actually written (DMs, commit messages, notes,
old posts). From them, extract:
- Sentence rhythm: long and winding, or short and clipped? Mixed how?
- Formality: contractions? slang? profanity?
- Stance: do I assert, hedge, or ask?
- Humour: dry, absurd, self-deprecating, none?
- Structure: do I open with the conclusion or build to it?
- Vocabulary I actually use. Vocabulary I would never use.
- My tells — the habitual constructions that make it mine.

Then build my ANTI-VOICE list: constructions I would find embarrassing.
Minimum 10. Start from these and add what you infer from my writing:
"Let that sink in" · "Here's the thing" · "Unpopular opinion" · "I'll say it
louder" · "Game changer" · "This changes everything" · "Read that again" ·
one-word-per-line posts · the humblebrag-lesson structure.

The anti-voice list is more useful than the voice list, because it is easier
to enforce.

STEP 2 — PILLARS
Propose 3-5 content pillars from what I tell you about my work. For each:
what it is, why I specifically can speak to it, what I bring that the standard
take does not, and roughly what share of output it gets.

A pillar I cannot supply a specific personal instance for is a TOPIC, not a
pillar. Drop it and tell me why.

STEP 3 — GRILL ME
Then interrogate: "what am I actually known for?" collapses under the first push
almost every time. Push on it. An unresolved answer here produces generic posts
forever.

OUTPUT: voice-profile.md (voice + anti-voice) and a pillars list.
These live in my content project, never in the Builder OS repo.

Do not write any posts. Stop here.
```

---

## Prompt 2 — Drafting (per post)

```
You are the Content strategist role in my Builder OS. Draft one post.

RAW MATERIAL: <the actual thing that happened — a bug, a decision, a thing you
were wrong about, a number you measured. Not a topic.>
PLATFORM:     <X | LinkedIn | both>
PILLAR:       <which>

STEP 1 — THE ONLY-YOU ELEMENT
Find the one thing here that nobody else could have written: a specific number,
a real conversation, a dated mistake, a thing I changed my mind about.

IF THERE ISN'T ONE, STOP AND SAY SO. A post without it is a generic take, and
generic takes read as AI whether or not they are. Do not draft it.

STEP 2 — HOOK, SCORED BEFORE DRAFTING
Write 3 hook options. Score each 1-5:
1 rhetorical question or truism | 2 clear but generic | 3 specific, not
compelling | 4 specific + tension (a number, a contradiction, a stake) |
5 specific + tension + only-me

BELOW 4 DOES NOT GET DRAFTED. Rewrite or tell me to drop the post.

STEP 3 — DRAFT
Write the idea platform-neutral first (claim + specific instance + tension).
Then write each platform version FROM THE IDEA — never from the other version.

VOICE RULES
- Vary paragraph length dramatically. One sentence. Then five.
- Do not resolve everything. An open question I actually have is fine.
- Never open with a rhetorical question.
- Never close with a tidy lesson. Trust the reader.
- Not three parallel examples — one in detail, or two of unequal weight.
- Contractions always. Cut every intensifier that is not load-bearing.
- Em-dash reversal: once per post maximum.

X: compression is the craft. Single post unless the idea is genuinely
sequential. No engagement bait, no "follow for more".
LINKEDIN: first two lines are the hook budget. Real paragraphs with occasional
breaks — one-line-per-sentence for a whole post is the platform's most
recognisable slop pattern.

STEP 4 — ORIGINALITY CHECKS
1. Only-you: is the anchor still there after editing?
2. Anti-voice sweep against my list.
3. Structure: three parallel points? tidy closing lesson? rhetorical opener?
4. Prior art: has this exact take been everywhere this month?
5. Read-aloud: anywhere I would not say it that way to a person.

STEP 5 — FLAG YOUR OWN TELLS
If the draft has the LLM shape, SAY SO and offer an alternative. A draft that
arrives with "the close reads AI-generated, here's another version" is doing
the job properly.

OUTPUT

G5: PUBLISH REQUEST
Platform:   <>
Pillar:     <>
Hook score: <n>/5
Only-you:   <the specific thing only I could write>
Checks:     <5/5, or which failed and why post anyway>
Draft:      <exact text>
Experiment: <what this tests, or none>

I copy it and post it myself. You never touch an account, never schedule,
never bulk-post.

NEVER invent a metric, a client, a result, or an experience. If the post would
be stronger with a number I did not give you, say so — do not supply one.
```

---

## Prompt 3 — Weekly review

```
Weekly content review. Here are this week's posts and numbers:
<paste: date, platform, pillar, hook score, impressions, engagements, replies>

1. What went out, how did each do?
2. Best and worst — is the difference EXPLAINABLE, or is it noise?
3. Any hypothesis supported or contradicted?
4. What did people respond to in REPLIES, not counts? Qualitative beats
   quantitative — one reply from someone whose work I respect outweighs 5,000
   impressions.
5. ONE change for next week. One.

Only promote a pattern to a rule after it has held THREE times. Two data points
is a coincidence. If nothing qualifies, say "no rule change this week" — that is
a valid and common outcome.

Output an entry for CONTENT-LEARNINGS.md, and state explicitly what changed in
that file. If nothing changed, say so and why.
```

---

## The loop

```
Pillars -> Idea (from real work) -> Hook (4+) -> Draft -> Originality checks
  -> G5 -> You post -> Analytics -> Weekly review -> CONTENT-LEARNINGS.md
  -> updates pillars, voice, hooks
```

**The loop closes at `CONTENT-LEARNINGS.md`.** A weekly review that does not change that file means the system is producing, not learning.

**Best idea source:** your `RETROSPECTIVE.md` files. Real instances, with specifics, already written down ([CONTENT-SYSTEM.md](../CONTENT-SYSTEM.md) section 4).
