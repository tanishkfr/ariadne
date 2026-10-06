# 22 — Minimal Creative Interruption

> **The user describes the outcome. Ariadne researches, explores, designs, builds, critiques
> and verifies.**
>
> **Ariadne should interrupt the human when meaning changes, not when padding changes.**

## The UX this replaces

```text
"Pick Editorial / Instrument / Cinematic"
"Should I search Mobbin?"
"Which design system should I use?"
"Do you want shadcn or 21st.dev?"
"Should I use cards?"
"Choose a font."
```

The user asked for a dashboard. How Ariadne obtains evidence is not a decision they are
qualified to make and certainly did not want to make. The tool's competence is precisely
that it can choose a source, a component, a spacing system and a capture plan unasked.

So the default is **automatic**, and interruption is the exception that has to earn its
place. That inverts the usual shape, where asking is cheap and proceeding is expensive.
Here proceeding is cheap — padding can be changed — and asking is expensive: an interruption
spends attention the user cannot get back.

## Three tiers

```text
AUTOMATIC      routine design, research, implementation and verification
CONDITIONAL    may proceed; must interrupt if meaning changes
HUMAN_REQUIRED  never proceed unattended
```

`AUTONOMOUS_DECISIONS` is deliberately long (23 entries): reference selection, concept
exploration, component choice, spacing, type and colour candidate evaluation, provider and
transport choice, capture planning, routine critique, bounded repair, test fixture and demo
content selection.

`HUMAN_REQUIRED_DECISIONS` is short (7). Every entry is a decision where proceeding
*unattended* would either change what the product means or exercise authority the user
holds. Every entry costs a real interruption, so an entry that could have been a routine
decision is a bug.

## Autonomy until meaning changes

Ariadne may change autonomously, inside an approved direction:

```text
padding · component implementation · responsive mechanics · hierarchy strength ·
existing approved motion details · copy inside an approved register · icon choice ·
spacing scale selection
```

Ariadne must stop when a proposed change alters:

```text
product meaning · brand identity · primary creative metaphor ·
navigation paradigm when direction-bound · major visual language · approved interaction model
```

The second list exists to make the first one meaningful. Without a stated boundary,
"autonomy until meaning changes" is unfalsifiable — everything can be called a meaning
change, and the policy silently becomes *ask the user about everything*.

### Meaning detection is structural, not phrase-matched

Matching the phrase *"navigation paradigm"* catches a policy document and no request ever.
The cue that actually occurs is *"replace the top navigation with a persistent sidebar"*, so
`meaning_triggers()` matches a **meaning noun** (`interruption.MEANING_NOUNS`) near a
**replacement verb** (`interruption.REPLACEMENT_VERBS`), in either order, within a short
window.

Both halves are mandatory, and getting that wrong is instructive. An earlier version made the
verb groups optional, which made *every bare mention* of "design system" a meaning change —
so the question the milestone brief explicitly forbids, *"which design system should I use"*,
became the one question the policy raised. A policy that raises the question it claims to
prevent is worse than no policy:

```text
a_bare_meaning_noun_without_a_replacement_is_not_a_meaning_change
```

Phrases covered: `replace` · `swap` · `change` · `different` · `instead of` · `rather than`
· `move away from` · `abandon` · `drop` · `no longer` — because *"swap to a completely
different visual language"* and *"drag instead of tap"* are how requests are actually
phrased, and a policy that only fires on "replace" protects nothing.

### Routine vocabulary

Terms and phrases from the brief's own list, checked **after** the human-required rules so a
change mentioning a component library *and* changing the brand is still a brand change:

```text
single terms   component, primitive, registry, library, adapter, transport, provider,
               spacing, padding, typeface, font, colour, palette, breakpoint, capture,
               typography, density, refactor, implementation, mechanics, responsive
phrases        design system, component library, implementation primitive, reference site,
               capture dimension, capture viewport, critique strategy, anti-slop rule,
               spacing system, colour system, type system, spacing scale, motion library
```

Phrases rather than words alone, because the individual words are too common: *"design"* and
*"system"* both appear in *"change the design system entirely"*, which **is** a meaning
change, and the phrase is what tells the two apart.

## G1D remains the meaningful boundary

`DIRECTION_APPROVAL_GATE = "G1D"` — the real engine gate, not a new mechanism. A proposal
approval routed through a parallel process could drift from it, and the weaker path is the
one that gets used. `proposal.approval_record()` wraps the real gate and records that it did.

## One interruption, verified

`interruption.assert_single_interruption()` is the inverse of a gate-existence test. Rather
than confirming a gate exists, it confirms the pipeline **did not need another one** — which
is the property the user actually experiences, and the one a gate-existence test cannot see.

The F1 vertical slice records seven post-approval decisions (implementation planning,
component and primitive choice, source provider choice, capture planning, content-model
refinement, responsive mechanics, typography candidate evaluation) and **zero**
interruptions:

```text
continuation: 7 decisions taken after approval with 0 interruption(s)
```

## See also

- [21 — Design Specificity Grammar](21-DESIGN-SPECIFICITY-GRAMMAR.md)
- [28 — AR-222D Results](28-AR-222D-RESULTS.md)
