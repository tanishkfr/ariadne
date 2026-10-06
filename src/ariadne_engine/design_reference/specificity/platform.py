"""Platform profiles: the boundary that keeps iOS rules out of universal design.

Every design system eventually absorbs the vocabulary of whatever platform somebody
last built for, and then quietly generalises it. SF Symbols becomes a design decision.
44pt becomes a spacing rule. A safe-area inset becomes a layout principle. Each hop is
individually reasonable and collectively the grammar stops describing design and starts
describing one platform.

So the two are separate records here, and the grammar may only cite the universal one:

```text
Design Specificity Grammar   what is true of any product on any surface
        +
Platform Profile            what is additionally true of one surface
```

A platform rule that has been justified on its own platform is *not* promoted by being
true. iPhone viewport dimensions are true of iPhone and false of a 27-inch display, and
that is not a matter of degree.

Three things follow, and they are the enforcement mechanism rather than a description of
one:

* :func:`platform_rule_leaks` names any platform-specific rule cited by a universal
  record. It is what the tests mutate.
* :func:`universal_defaults` is what a direction may assume with no platform named.
* :func:`profile_for` refuses a platform the build does not declare, rather than
  returning an empty profile that reads like permission.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from ...contracts import ContractError

PLATFORM_IDS = ("web", "desktop", "ios", "android", "spatial")
"""The profiles this build declares. A new platform is an entry, never a guess.

``web`` and ``desktop`` are universal-ish rather than universal: a desktop app has
window chrome and a menu bar that a web page does not. ``spatial`` exists so that a
future headset build has somewhere honest to put its rules, rather than smuggling them
into ``web``.
"""

PLATFORM_SPECIFIC_RULES: dict[str, tuple[str, ...]] = {
    "ios": (
        "safe-area insets for the notch, home indicator and dynamic island",
        "44pt minimum interactive control target",
        "SF Symbols as the icon vocabulary",
        "SwiftUI layout primitives and their sizing behaviour",
        "Liquid Glass material rendering",
        "UIScrollView keyboard-avoidance behaviour",
        "iPhone and iPad viewport dimensions",
        "app lifecycle and background-state transitions",
    ),
    "android": (
        "Material Design 3 elevation and dynamic colour",
        "48dp minimum interactive control target",
        "adaptive launcher and window size classes",
        "back-gesture and predictive-back behaviour",
        "Android viewport insets for cutouts and gesture bars",
    ),
    "spatial": (
        "volume-relative control sizing rather than pixel-relative",
        "reach and comfort envelopes for arm length",
        "stereo and focal-plane typography",
        "hands, gaze and voice as simultaneous input",
    ),
    "desktop": (
        "window chrome, menu bar and native file dialogs",
        "keyboard accelerator conventions",
        "pointer-device targets sized for a mouse rather than a finger",
        "multi-window and multi-monitor layout ownership",
    ),
    "web": (
        "viewport units and the document scroll container",
        "browser chrome changing the available height",
        "focus-visible heuristics for pointer and keyboard users",
    ),
}
"""Rules that are true *only inside* one platform's contract.

These are not banned. They are what a profile is for. The invariant is that none of
them may be cited as though it were a general principle of design.
"""

UNIVERSAL_DESIGN_RULES = (
    "hierarchy before decoration",
    "content before layout",
    "meaning before aesthetic adjective",
    "roles before literal values",
    "divergence before convergence",
    "a direction knows its own failure mode",
    "project identity outranks external inspiration",
    "render before judging",
    "critique arrives without the implementer's rationale",
)
"""What survives every platform change. Deliberately abstract: none of these is
expressible as a number, which is why none of them can leak a platform detail."""

_PLATFORM_TOKENS = tuple(
    sorted({
        token
        for rules in PLATFORM_SPECIFIC_RULES.values()
        for rule in rules
        for token in rule.lower().replace("-", " ").replace("/", " ").split()
        if len(token) > 3
    })
)


def platform_rule_leaks(*texts: str) -> list[str]:
    """Platform-specific rules cited by text that claims to be universal.

    Returns the offending phrases rather than a boolean, because a caller needs to
    say which rule leaked. Matching is over distinctive tokens rather than full
    strings: the same rule arrives in a dozen phrasings and a rule that can only be
    caught in its original wording is not a boundary.
    """
    found: list[str] = []
    for text in texts:
        if not str(text or "").strip():
            continue
        lowered = " ".join(str(text).lower().replace("-", " ").split())
        for platform, rules in PLATFORM_SPECIFIC_RULES.items():
            for rule in rules:
                tokens = [
                    token for token in rule.lower().replace("-", " ").split()
                    if len(token) > 3 and token not in ("and", "the", "for", "with", "than", "into")
                ]
                if tokens and all(token in lowered for token in tokens):
                    found.append(f"{platform}: {rule}")
    return sorted(set(found))


def profile_for(platform: str) -> dict:
    """The declared profile for one platform.

    An unknown platform raises. Returning an empty profile would be worse: the caller
    would proceed with no constraints and record that it had constraints.
    """
    name = str(platform or "").strip().lower()
    if name not in PLATFORM_IDS:
        raise ContractError(
            f"unknown platform profile {platform!r}; declare it before relying on it "
            f"(known: {', '.join(PLATFORM_IDS)})"
        )
    return {
        "platform": name,
        "rules": list(PLATFORM_SPECIFIC_RULES[name]),
        "universal": list(UNIVERSAL_DESIGN_RULES),
        "boundary": (
            "these rules are true of this platform only and are never promoted into the "
            "universal grammar; a different target platform re-derives its own"
        ),
    }


def universal_defaults() -> dict:
    """What a direction may assume when no platform is named."""
    return {
        "platform": "any",
        "rules": list(UNIVERSAL_DESIGN_RULES),
        "universal": list(UNIVERSAL_DESIGN_RULES),
        "boundary": "universal rules carry no platform-specific constraint",
    }


def assert_no_leak(*texts: str, label: str = "record") -> None:
    """Refuse a universal record that cites a platform rule as a general principle."""
    leaks = platform_rule_leaks(*texts)
    if leaks:
        raise ContractError(
            f"the {label} cites platform-specific rules as universal design principles: "
            + "; ".join(leaks)
            + ". Record it under a Platform Profile, or state the general principle the "
              "platform rule merely instantiates."
        )


def bound_platform_profiles(texts: Sequence[str], *, platform: str = "") -> dict:
    """Attach platform rules to a record, keeping them out of the universal body."""
    leaks = platform_rule_leaks(*texts)
    return {
        "universal_rules": list(UNIVERSAL_DESIGN_RULES),
        "platform_profile": str(platform),
        "platform_rules": list(PLATFORM_SPECIFIC_RULES.get(str(platform).lower(), ())),
        "platform_rule_citations": leaks,
        "platform_bound": bool(leaks) and not str(platform).strip(),
    }


__all__ = [
    "PLATFORM_IDS",
    "PLATFORM_SPECIFIC_RULES",
    "UNIVERSAL_DESIGN_RULES",
    "assert_no_leak",
    "bound_platform_profiles",
    "platform_rule_leaks",
    "profile_for",
    "universal_defaults",
]