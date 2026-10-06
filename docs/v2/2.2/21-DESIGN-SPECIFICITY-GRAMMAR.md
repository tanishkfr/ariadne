# 21 — Design Specificity Grammar

> **Ariadne has a house method, not a house style.**

AR-220 made a design direction *grounded*: every major choice cites inspected evidence.
Grounding turned out to be necessary and not sufficient, and the gap is where generated
design becomes interchangeable. A direction can cite six real references and still be "clean,
modern dashboard with card grid" — cited, actionable, and worthless.

The specific defect is one of ordering. The reflex is:

```text
"It's an F1 dashboard."  ->  dark, neon, technical  ->  done
```

The adjective arrives first, and once chosen it constrains everything downstream while
answering nothing about what an F1 dashboard is *for*.

## What this is

`ariadne_engine.design_reference.specificity` encodes **how to decide**, never **what to
look like**. It contributes no colour, no typeface, no spacing scale and no component.

That is enforced, not asserted. `grammar()` carries `house_style: None`, and
`grammar_problems()` refuses the record if anything fills that field in:

```text
a_grammar_that_has_collected_a_house_style_is_refused
```

The enforcement argument is worth stating plainly: a style would *have* to be encoded in the
methodology in order to be inherited by every future run, so it is made unrepresentable. A
test also asserts the grammar's structural data contains no literal design value — no
`#rrggbb`, no `12px`, no `font-family` — so the method cannot quietly accumulate an aesthetic
through its examples either.

## The twelve principles

In the order they constrain a decision (`grammar.PRINCIPLE_ORDER`):

| # | Principle | What it refuses |
|---|---|---|
| 1 | concept before aesthetic adjective | "editorial" as a starting point |
| 2 | content before layout | a layout designed for content nobody has |
| 3 | divergence before convergence | three options offered as a choice when there was one |
| 4 | roles before literal values | `#6d28d9` chosen before anyone asked what it was for |
| 5 | category defaults consciously chosen | a default nobody considered, silently arrived at |
| 6 | a direction knows its own failure mode | a direction with no local attractor named |
| 7 | richness source is specific | generic cards compensating for no named source |
| 8 | motion requires intent | `PREMIUM_ANIMATION` |
| 9 | project identity outranks external inspiration | a reference winning an argument the project should have |
| 10 | render before judging | reviewing a specification |
| 11 | fresh-eyes critique | the reviewer knowing what the worker intended |
| 12 | **restraint is a tool, not a goal** | austerity becoming its own house style |

The last one is the easiest to get wrong in either direction, so it is represented as data
(`ANTI_OVER_CORRECTION_AXES`) and enforced by `concepts.axis_spread_problems()` rather than
as an instruction.

## Roles before values

`meaning → role → implementation value`, generalised across colour, type and motion.

```text
colour   background, surface, surface_raised, primary_content, secondary_content,
         separator, accent_purpose, semantic_positive, semantic_caution, semantic_critical
type     display, navigation, body, metadata, data_metric
motion   SPATIAL_CONTINUITY, STATE_CONFIRMATION, AFFORDANCE,
         DIRECT_MANIPULATION, REWARD
```

Deliberately **not a token count**. Nine colour roles is what this vocabulary happens to
need; a product with three surfaces is not thereby wrong, and one with thirty states is not
thereby right.

`literal_value_first()` flags a binding with a value and no recorded meaning. That is a
warning about *process* — the value was chosen before the role's meaning was written down —
not proof that the value is wrong.

## Motion intent

Each intent carries the test that makes it a claim rather than an assertion
(`grammar.INTENT_EVIDENCE`). `SPATIAL_CONTINUITY`, for example, requires that the element
"appears from, or moves to, somewhere it previously occupied".

An animation mapping to none of the five is **suspect, not invalid**. Some motion establishes
physical presence, which is `SPATIAL_CONTINUITY` wearing a costume.

## Own-slop

Every direction names the cliché it collapses into when executed lazily
(`defaults.own_slop()`). The examples the milestone brief offers are exactly the right shape:

```text
editorial       -> generic cream + serif wellness
technical       -> terminal cosplay
automotive      -> neon HUD + fake speed lines
premium SaaS    -> monochrome cards + giant sans headline
AI              -> purple gradient + sparkles
```

These are *directions'* characteristic failures, not forbidden aesthetics. Recorded as a
prohibition (`own_failure_mode_banned`) the field is refused, because a direction that cannot
touch a cliché without collapsing is brittle in the other direction.

## Anti-over-correction

The failure this guards against is specific: **responding to generic AI design by producing
generic Ariadne design.** Six concepts arriving as "technical document" means the generator
found its own accent colour.

`grammar.ARIADNE_ATTRACTORS` names where Ariadne's own competence pulls: receipt, ledger,
ticket, terminal, control_panel, print_shop. Receipts are strong metaphors *because* Ariadne
keeps reaching for them, which is exactly why reaching is the risk.

`concepts.convergence_risk()` measures the collapse, and `concepts.axis_spread_problems()`
catches candidates that agree on one axis even when no attractor word appears — the set that
is all editorial, or all monochrome, or all sparse.

## Content before layout

A layout chosen before its content is a layout for content nobody has. `content.py` holds a
content model with three honesty rules:

* **No `lorem ipsum`.** A layout validated against filler has been validated against nothing.
* **No suspiciously perfect data.** Every value identical, every value round, every value the
  same length — the other filler, and more dangerous because it looks like a real screenshot.
* **The states are content.** Empty, loading and error are not exceptions to a content model;
  they are the cases whose layout nobody checked.

Ranges, not samples: a model records the realistic *span* of what will appear, so a layout is
tested against the worst plausible value rather than the friendliest.

`content_layout_precedence()` refuses a layout plan whose content model is missing, unusable,
or recorded *after* the plan — with the ordering steps recorded so it is auditable rather
than asserted.

### Believable demo content is a design technique, not permission to fabricate

`fabrication_findings()` reports content specific enough to be mistaken for a factual claim:
a live URL, a real-company name, an email address, a precise date. Believable demo content
makes a design legible; it does not license claiming a real person, company, measurement or
outcome.

## See also

- [22 — Minimal Creative Interruption](22-MINIMAL-CREATIVE-INTERRUPTION.md)
- [24 — Platform Design Profiles](24-PLATFORM-DESIGN-PROFILES.md)
- [25 — Proof Readiness](25-PROOF-READINESS.md)
- [28 — AR-222D Results](28-AR-222D-RESULTS.md)
