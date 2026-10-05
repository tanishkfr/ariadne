"""Design Specificity Grammar and source ecosystem (AR-222D).

AR-220 made a design direction *grounded*: every major choice cites inspected evidence.
Grounding is necessary and not sufficient, and the gap between the two is where generated
design becomes interchangeable -- a direction can cite six real references and still be
"clean, modern dashboard with card grid". Cited, actionable, and worthless.

So this package answers a second question AR-220 did not ask:

> **Is this direction specific, and was any of it decided?**

with a methodology rather than an aesthetic. The product principle it implements:

> **Ariadne has a house method, not a house style.**
>
> **Specificity is the goal. Restraint is only a tool.**
>
> **A pattern is not bad because it is common; it is bad when nobody decided why it belongs.**

Nothing in this package can be rendered. There is no colour here, no typeface, no spacing
scale and no component, and :func:`grammar` carries an explicit ``house_style: null`` that
:func:`grammar.grammar_problems` refuses if a future edit fills in. That is the
enforcement mechanism for the difference between a method and a style: a style would have
to be encoded here to be inherited by every future run, so it is made unrepresentable.

The eight modules:

===================  =============================================================
:mod:`grammar`       the twelve decision principles, role vocabularies, motion intents
:mod:`concepts`      concept-first exploration, material divergence, anti-over-correction
:mod:`content`       content before layout, filler and fake-perfect-data detection
:mod:`defaults`      category defaults as contextual patterns; detection != failure
:mod:`platform`      universal grammar vs platform profile, and the leak check between
:mod:`interruption`  autonomy until meaning changes; when the human may be interrupted
:mod:`proposal`      the provider-neutral direction proposal a human actually approves
:mod:`sources`       the verified source ecosystem: role, capability, honest availability
===================  =============================================================

Two of those deserve their invariant stated at the top, because both are routinely
implemented as their opposite:

* :mod:`defaults` -- a detected pattern is **not** a failure. Cards, dark interfaces,
  purple and glass are all frequently correct. The system attacks *unexamined defaults*, and
  the only actionable state a detection can produce is ``UNEXAMINED``: present, and nobody
  decided.
* :mod:`sources` -- **a registry entry is not an integration.** Thirty-nine sources are
  registered; ten have a defensible automated path. That gap is the honest answer, and it
  is recorded per source rather than smoothed by building thirty-six scrapers.

And the sentence the whole phase is for:

> **Ariadne should interrupt the human when meaning changes, not when padding changes.**
"""

from __future__ import annotations

from . import (
    concepts,
    content,
    defaults,
    grammar,
    interruption,
    platform,
    proposal,
    sources,
    vertical_slice,
)

GRAMMAR_ID = "design-specificity-grammar-1"


def methodology() -> dict:
    """The whole methodology, as one record a run can carry and a test can assert."""
    return {
        "grammar": grammar.grammar(),
        "interruption_policy": interruption.policy(),
        "default_patterns": defaults.registry(),
        "source_ecosystem": {
            "count": sources.registry()["count"],
            "by_status": sources.registry()["by_status"],
            "verified_at": sources.VERIFIED_ON,
        },
        "platform_boundary": platform.universal_defaults(),
        "invariants": [
            "ariadne has a house method, not a house style",
            "specificity is the goal; restraint is only a tool",
            "a pattern is not bad because it is common; it is bad when nobody decided why it belongs",
            "references inform design; they do not replace design thinking",
            "tools are chosen by ariadne, not operated by the user",
            "autonomy until meaning changes",
            "workers produce; independent systems establish evidence; humans retain creative and acceptance authority",
        ],
    }


__all__ = [
    "GRAMMAR_ID",
    "concepts",
    "content",
    "defaults",
    "grammar",
    "interruption",
    "methodology",
    "platform",
    "proposal",
    "sources",
    "vertical_slice",
]
