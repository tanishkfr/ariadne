# 04 — The DESIGN.md Format (AR-220)

Ariadne consumes `DESIGN.md` as an **input format**. It is not Ariadne's internal
canonical schema, and this module never lets it become one:

```text
DESIGN.md ──▶ parse_design_md ──▶ raw token/rationale blocks ──▶ DesignReference
   (someone else's format)      (not Ariadne's schema)
```

## The specification, and what is actually published

`DESIGN.md` was introduced by **Google Stitch** as a plain-text design-system
document for AI agents. The specification pages are at
`stitch.withgoogle.com/docs/design-md/overview/` and `.../specification/`.

Stitch's own framing, quoted from the maintainers' collection README:

> *"[DESIGN.md](https://stitch.withgoogle.com/docs/design-md/overview/) is a new
> concept introduced by Google Stitch. A plain-text design system document that AI
> agents read to generate consistent UI.*
>
> *It's just a markdown file. No Figma exports, no JSON schemas, no special tooling.
> Drop it into your project root and any AI coding agent or Google Stitch instantly
> understands how your UI should look."*

### The extension in circulation

The published corpus extends Stitch's shape with a nine-section contract, and
states the extension explicitly:

> *"Every file follows the [Stitch DESIGN.md format] with extended sections"*

| # | Section | Captures |
|---|---------|----------|
| 1 | Visual Theme & Atmosphere | mood, density, design philosophy |
| 2 | Colour Palette & Roles | semantic name + hex + functional role |
| 3 | Typography Rules | font families, full hierarchy |
| 4 | Component Stylings | buttons, cards, inputs, navigation with states |
| 5 | Layout Principles | spacing scale, grid, whitespace philosophy |
| 6 | Depth & Elevation | shadow system, surface hierarchy |
| 7 | Do's and Don'ts | design guardrails and anti-patterns |
| 8 | Responsive Behaviour | breakpoints, touch targets, collapsing strategy |
| 9 | Agent Prompt Guide | quick colour reference, prompts |

Ariadne recognises these as a **vocabulary, not a requirement**:
`designmd.DOCUMENT_SECTIONS` records which were present and which are missing, and a
project `DESIGN.md` with four sections is recorded honestly rather than refused.

## Shape Ariadne supports

```yaml
---
version: alpha
name: Linear-design-analysis
description: |
  A near-black product-focused canvas built around #010102 …

colors:
  primary: "#5e6ad2"
  canvas: "#010102"
  hairline: "#23252a"
typography:
  body:
    fontFamily: Linear Text
    fontSize: 16px
    fontWeight: 400
    letterSpacing: -0.05px
rounded:
  md: 5px
spacing:
  lg: 16px
components:
  text-input:
    backgroundColor: "{colors.surface-1}"
    rounded: "{rounded.md}"
    padding: 8px 12px
---

## Overview
…human-readable rationale…

## Do's and Don'ts
- Do keep separators hairline-thin.
- Don't introduce glassmorphic cards.
```

Supported subset: nested mappings, block lists, inline `[a, b]` lists, quoted and
bare scalars, `|`/`>` block scalars, and `{group.name}` token references.

## Parser design, and why each decision

Ariadne core is standard-library only (`pyproject.toml` declares
`dependencies = []`). So this is a **bounded subset parser**, not a YAML
implementation, and it is written to be auditable.

| Decision | Reason |
|----------|--------|
| No PyYAML | Keeps the core dependency-free. A full YAML engine is a large attack surface for a document format we only partly need. |
| **Duplicate keys refused** | A document that defines `primary` twice has two values and one meaning. Keeping the last silently would make the parsed record disagree with the bytes while both carry the same digest. |
| **Oversized input refused** | `MAX_DESIGN_REFERENCE_BYTES` = 256 KiB. Refused with a named reason, never truncated — a truncated record looks complete and is not. |
| **Unknown fields preserved** | `unknown_fields` + a warning. The rationale in a design document is usually the part Ariadne does not model and the part most worth keeping. |
| Anchors/aliases/tags/directives refused | Expansion and state gadgets with no place in a design document. `*base` can turn one line into an unbounded graph walk. |
| Tab indentation refused | YAML forbids it; ambiguous structure must not slip past the parser. |
| Nesting bounded | 12 levels. Unbounded recursion on attacker-supplied input is a denial of service. |
| Malformed input refused **by name** | A half-parsed token table carrying a valid digest is worse than no record. |

### Three format features the real corpus forced

All three were discovered by running the parser against live documents, not by
reading a spec:

1. **Literal block scalars** (`description: |`). Every long rationale in the
   published corpus uses one. A parser that cannot read them sees *no description at
   all* on most documents — a silent, total failure.
2. **Non-ASCII plain keys** (`属于:`). The Raycast document carries a Chinese
   "belongs to" field. Refusing it would have meant refusing a published document
   over a field name. Keys are Unicode-aware; unrecognised keys are preserved.
3. **A UTF-8 BOM.** A `DESIGN.md` committed with a BOM opens with `\ufeff---`, not
   `---`. A parser that does not strip it concludes the document has no frontmatter
   and reports **zero tokens** while still recording a correct content digest. This
   is the worst kind of bug: it looks like "this document has no tokens" rather
   than "this parser is broken".

Also worth noting what *did not* break: markdown emphasis. `**bold**`, `_italic_`
and `## Do's and Don'ts` in the rationale body are ordinary prose, so the YAML
construct scan is scoped to the **frontmatter block** and to YAML *token positions*.
An earlier version scanned the whole document and refused the corpus on
`**Linear**`. That failure mode — a safety check silently destroying the thing it
protects — is worse than the risk it guards against.

## Token references

`{colors.surface-1}` is resolved **by name only**, with a depth bound. It never
touches the filesystem, never evaluates an expression, and never raises on a
dangling reference — a document may legitimately name a token it does not define.
Resolution is recorded so a direction can say how many references resolved:

```text
linear.app.md → 84 token references, 84 resolved, 0 dangling
```

## Sections

Headings are matched on their **own text**, not on a CSS or DOM selector, so a
markdown document is parsed by its markdown structure. Slugs come from
`slugify_heading`, which is the single source of truth for section identity — an
earlier vocabulary said `dos-and-donots` while the heading slugifies to
`dos-and-donts`, which reported *every* document as missing its do/don't section.
That is a false negative about the section most likely to carry anti-pattern
guidance, caused by a vocabulary that had drifted from its slugifier.

## Validation

`designmd.validation_problems` reports **structural** problems:

- no machine-readable frontmatter;
- no declared `name`, so the document has no stable identity;
- no recognised token group;
- dangling token references;
- no rationale sections, so the document records no reasoning;
- an unusable `version` string.

Validation is separate from parsing, so a *structurally dangerous* document is
refused while an *incomplete* one is merely reported. Useful design reasoning that
Ariadne does not model must not be thrown away.

An external validator or CLI may be used optionally. None is required; Ariadne does
not install one.

## Security properties

Tested directly (see `06-REFERENCE-SECURITY.md`):

| Attack | Refusal |
|--------|---------|
| Oversized document | `MAX_DESIGN_REFERENCE_BYTES`, refused not truncated |
| Duplicate keys | refused by line number |
| Unclosed frontmatter | refused by name |
| Tab indentation | refused |
| YAML anchor / alias / tag / directive | refused by construct name |
| Excessive nesting | refused |
| Duplicate keys hiding behind Unicode | same duplicate-key path |
| Markdown links carrying `javascript:` | link text is stored as inert text; URLs are never fetched from a document |

## What Ariadne does *not* consume

Stitch's `AGENTS.md` companion (how to build the project) is probed for Figma links
and nothing else. Screenshots, Figma exports, JSON schemas and agent prompt guides
are not parsed. A `DESIGN.md` is prose plus tokens; Ariadne reads the tokens as
observations and the prose as rationale, and refuses to act on either as an
instruction.