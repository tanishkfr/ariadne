"""Category defaults as contextual patterns, not banned styles (AR-222D).

The tempting implementation of "avoid generic design" is a blocklist: no cards, no
purple, no glass, no dark mode. It is wrong in a way that is easy to miss, because it
produces the same visual outcome with more effort and a worse rationale.

Cards may be correct. Dark interfaces may be correct. Purple may be correct. A product
whose entire domain is tabular records *should* be a grid of rows. Blocking the grid
would not improve it.

So a default is represented as a **contextual pattern** -- a set of signals, the
domain contexts where it is usually generic, the conditions under which it is valid,
and the question to ask instead of a rule to obey:

```text
DesignDefaultPattern
    pattern_id, signals, domain_context, why_generic
    valid_when, alternative_question
    deterministic_detectors, requires_visual_judgment
```

and the adjudication is the load-bearing part:

```text
pattern detected  ≠  design failure
```

The question is never "is this pattern present". It is **was this choice earned** -- by
the product, the requirement or the direction. :func:`adjudicate` answers that, and a
detected pattern with a recorded justification is ``EARNED``, not a defect. A detected
pattern with no justification is ``UNEXAMINED``, which is the only genuinely actionable
state here.

Two consequences are worth stating because they are what keep this from becoming a
blocklist in disguise:

* :data:`DESIGN_DEFAULT_PATTERNS` contains no rule that can be expressed as "never use".
  Every entry carries ``valid_when``, because a pattern that is never valid is a ban
  wearing a pattern's clothes.
* Deterministic detectors are *probes*, and what they produce is a detection, never a
  verdict. Anything a string match cannot settle sets ``requires_visual_judgment`` and
  is handed to a human.
"""

from __future__ import annotations

import re
from typing import Mapping, Sequence

from ...contracts import ContractError
from . import grammar as grammar_module

DETECTION_VERDICTS = ("EARNED", "UNEXAMINED", "CONTRADICTED", "NOT_PRESENT")
"""What can be concluded from a detection.

``EARNED``         present, and the product/requirement/direction required it
``UNEXAMINED``     present, and nobody decided. This is the only actionable state
``CONTRADICTED``   present, and it contradicts something the direction says
``NOT_PRESENT``    not detected. Says nothing about quality either way
"""

UNEXAMINED = "UNEXAMINED"

DEFAULT_PATTERN_FIELDS = (
    "pattern_id",
    "signals",
    "domain_context",
    "why_generic",
    "valid_when",
    "alternative_question",
    "deterministic_detectors",
    "requires_visual_judgment",
)
"""The shape of every pattern. Enforced, because a pattern missing ``valid_when`` is a
ban, and a ban is the failure mode this module exists to prevent."""


def _pattern(
    pattern_id: str,
    signals: Sequence[str],
    domain_context: Sequence[str],
    why_generic: str,
    valid_when: Sequence[str],
    alternative_question: str,
    detectors: Sequence[str],
    *,
    requires_visual_judgment: bool = False,
) -> dict:
    return {
        "pattern_id": str(pattern_id),
        "signals": [str(item) for item in signals],
        "domain_context": [str(item) for item in domain_context],
        "why_generic": str(why_generic),
        "valid_when": [str(item) for item in valid_when],
        "alternative_question": str(alternative_question),
        "deterministic_detectors": [str(item) for item in detectors],
        "requires_visual_judgment": bool(requires_visual_judgment),
    }


DESIGN_DEFAULT_PATTERNS: tuple[dict, ...] = (
    _pattern(
        "dashboard-reflex",
        (
            "every surface resolves into a header, a filter bar and a panel grid",
            "no surface states what it is for",
            "the layout would be identical for a scheduler and a race telemetry console",
        ),
        ("analytics", "admin", "operations", "reporting", "monitoring"),
        "the dashboard arrangement is available as a prior, so nothing has to be decided about "
        "how the product should actually read",
        (
            "the product's domain genuinely is a set of monitored panels",
            "the arrangement is inherited from an existing system the team must match",
            "the constraints force it and the record says so",
        ),
        "what does this product need to be legible about that a panel grid cannot show?",
        ("panel-grid-for-every-surface", "header-plus-filterbar-precedes-purpose"),
    ),
    _pattern(
        "everything-is-a-card",
        (
            "distinct content types are wrapped in identical rounded rectangles",
            "elevation is used where hierarchy could be expressed by space or type",
            "a row of text and a chart receive the same container treatment",
        ),
        ("dashboard", "admin", "saas", "settings", "listing"),
        "the card is a container that has to work for everything, so it is used for everything",
        (
            "the content really is repeated independent units that need individual selection",
            "the grouping is genuinely semantic and not merely visual",
            "the design system defines card as a meaningful component",
        ),
        "which of these elements are actually independent units, and which are just grouped?",
        ("uniform-card-containers", "card-count-equals-element-count"),
    ),
    _pattern(
        "three-stat-row",
        (
            "exactly three headline metrics sit above the content with equal weight",
            "the numbers chosen are the three that were easy to count",
            "no dimension of the product is represented in the summary",
        ),
        ("analytics", "dashboard", "monitoring", "admin"),
        "three equal tiles is the shape a summary defaults to when nobody has said what matters",
        (
            "the product has exactly three co-equal primary measures and no others",
            "the arrangement is required by an existing system",
            "the numbers were chosen by analysis and the record shows it",
        ),
        "what are the two or three numbers someone would act on, and why are those?",
        ("exactly-three-headline-metrics", "equal-weight-summary-tiles"),
    ),
    _pattern(
        "generic-greeting",
        (
            "welcome copy addresses the user by default",
            "empty states restate the product name",
            "the first thing on the surface is a greeting rather than work",
        ),
        ("dashboard", "onboarding", "saas", "admin"),
        "a greeting costs a whole row of hierarchy and produces no information",
        (
            "the product genuinely has a per-user session worth acknowledging",
            "an existing brand requires it",
        ),
        "what is the first useful thing this surface could say?",
        ("welcome-or-greeting-first-visible",),
    ),
    _pattern(
        "uniform-spacing",
        (
            "one spacing value appears between every kind of element",
            "related and unrelated elements are equally separated",
            "the scale has values but nothing selects between them",
        ),
        ("any",),
        "a single interval is the point at which no decision was made about proximity, and proximity "
        "is the cheapest hierarchy available",
        (
            "the content genuinely has uniform relationships",
            "a design system mandates a uniform base and the density requirement is real",
        ),
        "which pairs of elements are related, and which are merely adjacent?",
        ("single-spacing-value-across-roles",),
        requires_visual_judgment=True,
    ),
    _pattern(
        "fake-depth",
        (
            "shadows are used on elements that are not actually above anything",
            "borders and shadows are stacked rather than chosen",
            "elevation implies a stacking order the layout does not have",
        ),
        ("dashboard", "admin", "mobile", "web"),
        "depth implies hierarchy; applying it decoratively spends the hierarchy signal on nothing",
        (
            "the surface genuinely has layered planes (a menu above content, a modal above a page)",
            "the depth is a real physical affordance in the metaphor",
        ),
        "is anything actually above anything else here?",
        ("shadow-on-non-layered-element", "border-plus-shadow-on-same-element"),
    ),
    _pattern(
        "random-glass",
        (
            "backdrop-filter is applied where no content passes behind the surface",
            "translucency decorates rather than communicating a layer",
            "every surface is blurred, so none of them denotes anything",
        ),
        ("web", "mobile", "dashboard", "landing"),
        "translucency only communicates where there is something behind. Applied everywhere it "
        "communicates nothing and costs performance",
        (
            "content genuinely passes behind the surface and the layer needs to be readable",
            "the physical metaphor genuinely involves a translucent material",
            "a platform mandates the material treatment",
        ),
        "what is behind this surface, and does the user need to see it?",
        ("backdrop-filter-without-behind-content", "translucency-on-every-layer"),
    ),
    _pattern(
        "generic-ai-gradient",
        (
            "a violet-to-blue gradient carries no semantic load",
            "gradient text is applied to a heading for emphasis",
            "the palette is the recognisable default assistant aesthetic",
        ),
        ("landing", "saas", "marketing", "onboarding"),
        "the gradient is a recognisable signal for machine-generated work, so it reads as a "
        "missing decision rather than a choice",
        (
            "the product's identity genuinely is this palette",
            "a brand system specifies it",
            "the gradient encodes something real, and the record says what",
        ),
        "does this colour choice mean anything, or is it decoration wearing meaning's clothes?",
        ("violet-blue-gradient-without-semantics", "gradient-text-heading"),
    ),
    _pattern(
        "default-font-palette-combo",
        (
            "a default sans with the default neutral palette",
            "type and colour were never individually chosen",
            "both are whatever the framework or template shipped with",
        ),
        ("any",),
        "the default is not a choice; it is the absence of one, and it is the same absence in every "
        "generated product",
        (
            "the project already ships these and changing them would exceed scope",
            "the platform constrains the available fonts",
            "the combination is the project's established identity",
        ),
        "what does this product need from its type, and what from its colour?",
        ("framework-default-font", "framework-default-palette"),
    ),
    _pattern(
        "meaningless-icon-chips",
        (
            "icons appear beside text that already says the same thing",
            "chips carry no filter, category or state",
            "the icon is a different set from the words it labels",
        ),
        ("dashboard", "admin", "listing", "mobile"),
        "an icon is read as a compact category or state; an icon beside its own label carries "
        "nothing and adds a second thing to maintain",
        (
            "the icon is a recognised category marker the words do not establish",
            "it carries state the text omits",
            "it is a required affordance for the target platform",
        ),
        "does this icon carry meaning the text does not, or is it decorating its own caption?",
        ("icon-adjacent-to-identical-label", "chip-without-filter-semantics"),
    ),
    _pattern(
        "generic-stock-imagery",
        (
            "photography of people stock-looking at laptops",
            "abstract gradients standing in for a product",
            "the imagery could belong to any product in the category",
        ),
        ("landing", "marketing", "onboarding"),
        "stock imagery is chosen to fill a slot, so it asserts a use case nobody confirmed",
        (
            "the imagery is genuine product photography or a real customer",
            "a brand system specifies it and the rights are held",
        ),
        "is this image evidence of this product, or is it filling a slot?",
        ("stock-photography-detected", "abstract-image-in-product-slot"),
    ),
    _pattern(
        "fake-perfect-data",
        (
            "every value is round",
            "every value in a series is identical",
            "nothing is ever empty, loading, partial or wrong",
        ),
        ("dashboard", "analytics", "monitoring", "demo", "fixture"),
        "perfect data is an assertion the product never makes, and it hides every layout case that "
        "matters",
        (
            "the product genuinely cannot reach the states being shown",
            "the screenshot is explicitly labelled as synthetic and the label is visible",
        ),
        "what does this look like when the data is incomplete or the service is degraded?",
        ("all-values-round", "all-series-identical", "no-empty-or-error-state-shown"),
    ),
    _pattern(
        "marketing-copy-in-product-ui",
        (
            "product surfaces use headline-style copy",
            "a feature announcement sits above the working controls",
            "the interface explains why it is great instead of doing its job",
        ),
        ("product", "dashboard", "admin", "settings"),
        "marketing register inside a working surface costs the user the thing they came for",
        (
            "the surface is genuinely an onboarding or announcement surface",
            "a required disclosure must appear here",
        ),
        "is this surface where someone works, or where someone is persuaded?",
        ("headline-register-on-working-surface",),
        requires_visual_judgment=True,
    ),
    _pattern(
        "motion-on-load-without-state-change",
        (
            "content animates in on every visit",
            "the entrance animation repeats identically with no state change behind it",
            "nothing about the data or the interaction has changed, and it animates anyway",
        ),
        ("web", "mobile", "landing", "dashboard"),
        "entrance motion is justified by a state change. Repeating it for every visit spends attention "
        "on a transition that means nothing",
        (
            "the animation establishes spatial continuity for content that genuinely arrived",
            "the platform has no persistent state and the transition is honest about new content",
        ),
        "what state changed, and is the motion showing that change?",
        ("entrance-animation-without-state-change",),
    ),
)

PATTERNS_BY_ID = {row["pattern_id"]: row for row in DESIGN_DEFAULT_PATTERNS}


def pattern_problems(record: Mapping) -> list[str]:
    """A pattern must carry the fields that stop it functioning as a ban."""
    problems: list[str] = []
    for name in DEFAULT_PATTERN_FIELDS:
        if name not in record:
            problems.append(f"design default pattern has no {name}")
    if not str(record.get("pattern_id", "")).strip():
        problems.append("a design default pattern is named")
    if not [item for item in (record.get("signals") or []) if str(item).strip()]:
        problems.append("a design default pattern names the signals that indicate it")
    if not [item for item in (record.get("valid_when") or []) if str(item).strip()]:
        problems.append(
            "a design default pattern states when the pattern is correct. A pattern with no valid "
            "case is a ban, and a ban is what this model exists to avoid"
        )
    if not str(record.get("alternative_question", "")).strip():
        problems.append(
            "a design default pattern carries the question to ask instead of a rule to obey"
        )
    if not str(record.get("why_generic", "")).strip():
        problems.append("a design default pattern explains why it tends to be generic")
    return list(dict.fromkeys(problems))


def registry() -> dict:
    """Every known category default, with its honest uncertainty."""
    return {
        "patterns": [dict(row) for row in DESIGN_DEFAULT_PATTERNS],
        "count": len(DESIGN_DEFAULT_PATTERNS),
        "verdicts": list(DETECTION_VERDICTS),
        "invariant": "pattern detected != design failure",
        "method": (
            "attack unexamined defaults, not aesthetics. Cards, dark interfaces, purple and glass may "
            "all be correct; what is not acceptable is any of them arriving without a decision"
        ),
    }


def _looks_like_a_ban(record: Mapping) -> list[str]:
    """Bans phrased as patterns: ``valid_when`` entries that are really prohibitions."""
    problems: list[str] = []
    for entry in (record.get("valid_when") or []):
        text = str(entry).strip().lower()
        if text.startswith(("never ", "no ", "don't ", "do not ", "avoid ")):
            problems.append(
                f"valid_when entry {str(entry)!r} is phrased as a prohibition. If the pattern has no "
                "valid case it is a ban, and a ban is not this model"
            )
    return problems


def detect(
    subject: str,
    *,
    patterns: Sequence[Mapping] | None = None,
    detectors: Mapping[str, Sequence[str]] | None = None,
) -> list[dict]:
    """Probe a subject for known category defaults. Detections only, never verdicts.

    A deterministic detector matches text. What a text match can establish is that a
    token is present, and that is all this returns -- every entry carries
    ``requires_visual_judgment`` so a human or a model finishes the judgement.

    The word "detected" in every record of this function is load-bearing. Detection is
    cheap, common, and not evidence of a problem.
    """
    rows: list[dict] = []
    haystack = " ".join(str(subject or "").lower().replace("_", " ").split())
    pool = tuple(patterns) if patterns is not None else DESIGN_DEFAULT_PATTERNS
    supplied = detectors if isinstance(detectors, Mapping) else {}
    for pattern in pool:
        if not isinstance(pattern, Mapping):
            continue
        pattern_id = str(pattern.get("pattern_id", ""))
        matched: list[str] = []
        for token in supplied.get(pattern_id) or ():
            if str(token).lower() in haystack:
                matched.append(str(token))
        signals = [
            str(signal) for signal in (pattern.get("signals") or [])
            if _signal_present(str(signal), pattern_id, haystack)
        ]
        hits = sorted(set([*matched, *signals]))
        if not hits:
            rows.append({
                "pattern_id": pattern_id,
                "detected": False,
                "signals_matched": [],
                "requires_visual_judgment": bool(pattern.get("requires_visual_judgment", False)),
                "verdict": "NOT_PRESENT",
                "justification": "",
                "note": "no signal found. This says nothing about whether the pattern would be correct here",
            })
            continue
        rows.append({
            "pattern_id": pattern_id,
            "detected": True,
            "signals_matched": hits,
            "requires_visual_judgment": bool(pattern.get("requires_visual_judgment", False)),
            "verdict": UNEXAMINED,
            "justification": "",
            "alternative_question": str(pattern.get("alternative_question", "")),
            "why_generic": str(pattern.get("why_generic", "")),
            "valid_when": list(pattern.get("valid_when") or []),
            "note": (
                "detected is not failed. The question is whether this choice was earned by the "
                "product, the requirement or the direction"
            ),
        })
    return rows


_SIGNAL_TOKENS = {
    "dashboard-reflex": ("panel", "panels", "grid", "filter-bar", "sidebar"),
    "everything-is-a-card": ("card", "cards"),
    "three-stat-row": ("stat", "stats", "kpi", "metric", "metrics"),
    "generic-greeting": ("welcome", "hello", "good morning", "greeting"),
    "uniform-spacing": ("gap", "spacing", "padding", "margin"),
    "fake-depth": ("shadow", "box-shadow", "elevation", "drop-shadow"),
    "random-glass": ("backdrop-filter", "glass", "blur", "frosted"),
    "generic-ai-gradient": ("gradient", "linear-gradient", "radial-gradient", "violet", "purple"),
    "default-font-palette-combo": ("font-family", "system-ui", "sans-serif", "neutral"),
    "meaningless-icon-chips": ("icon", "chip", "badge", "pill"),
    "generic-stock-imagery": ("stock", "unsplash", "shutterstock", "hero-image"),
    "fake-perfect-data": ("demo-data", "sample-data", "mock", "placeholder-data"),
    "marketing-copy-in-product-ui": ("cta", "sign-up", "get-started", "discover"),
    "motion-on-load-without-state-change": ("animation", "animate", "fade-in", "keyframe"),
}
"""Probes per pattern, kept beside the patterns rather than inside their prose.

The signals themselves are sentences a human can argue with, which is the point -- but a
sentence cannot be matched against a stylesheet. These tokens are the *cheap* half of
detection and they exist so a probe can run without a model. Everything they find is
still only a detection.
"""


def _signal_present(signal: str, pattern_id: str, haystack: str) -> bool:
    """Whether one prose signal is corroborated by a cheap lexical probe.

    Tokens are per-pattern rather than per-signal because the signals are prose: "a
    shadow implies a stacking order" and "borders and shadows are stacked" both warrant
    looking for ``shadow`` once.
    """
    tokens = _SIGNAL_TOKENS.get(pattern_id, ())
    if not tokens:
        return False
    for token in tokens:
        if re.search(rf"\b{re.escape(token)}\b", haystack):
            return True
    return False


def adjudicate(
    detections: Sequence[Mapping],
    *,
    justification: Mapping[str, str] | None = None,
    direction_contradictions: Mapping[str, str] | None = None,
) -> list[dict]:
    """Decide whether each detected pattern was earned.

    This is where ``detected != failure`` becomes behaviour rather than a slogan. The
    only state that produces work is ``UNEXAMINED`` -- present with nobody having
    decided -- and even that produces a *question*, not a removal.
    """
    reasons = justification if isinstance(justification, Mapping) else {}
    contradictions = direction_contradictions if isinstance(direction_contradictions, Mapping) else {}
    rows: list[dict] = []
    for detection in detections or ():
        if not isinstance(detection, Mapping):
            continue
        record = dict(detection)
        pattern_id = str(record.get("pattern_id", ""))
        if not bool(record.get("detected")):
            rows.append(record)
            continue
        contradiction = str(contradictions.get(pattern_id, "")).strip()
        reason = str(reasons.get(pattern_id, "")).strip()
        if contradiction:
            record["verdict"] = "CONTRADICTED"
            record["justification"] = reason
            record["contradiction"] = contradiction
        elif reason:
            record["verdict"] = "EARNED"
            record["justification"] = reason
        else:
            record["verdict"] = UNEXAMINED
            record["justification"] = ""
        rows.append(record)
    return rows


def unexamined(detections: Sequence[Mapping]) -> list[str]:
    """The patterns that are present and nobody decided about. The whole actionable set."""
    return sorted(
        str(row.get("pattern_id", ""))
        for row in detections or ()
        if isinstance(row, Mapping)
        and bool(row.get("detected"))
        and str(row.get("verdict", "")) == UNEXAMINED
    )


def anti_slop_report(
    detections: Sequence[Mapping],
    *,
    direction: Mapping | None = None,
    candidate_directions: Sequence[Mapping] | None = None,
) -> dict:
    """Anti-default analysis that cannot force an austere answer.

    Two asymmetries, both deliberate:

    * ``EARNED`` detections are reported as **kept on purpose**. Removing them because
      they match a known pattern would be anti-slop analysis behaving exactly like the
      cliché it claims to avoid.
    * A direction with no ``richness_source`` is reported as a hole regardless of how
      few defaults it triggered. A design that trips no pattern by being empty is not
      thereby specific.
    """
    rows = list(detections or [])
    present = [row for row in rows if isinstance(row, Mapping) and bool(row.get("detected"))]
    kept = [row for row in present if str(row.get("verdict")) == "EARNED"]
    questioned = [row for row in present if str(row.get("verdict")) == UNEXAMINED]
    contradicted = [row for row in present if str(row.get("verdict")) == "CONTRADICTED"]
    problems = grammar_module.richness_problems(direction or {})
    restraint = str((direction or {}).get("richness_source", "")).upper() in (
        grammar_module.RESTRAINT_RICHNESS_SOURCES
    )
    return {
        "detected": len(present),
        "earned": sorted(str(row.get("pattern_id", "")) for row in kept),
        "unexamined": sorted(str(row.get("pattern_id", "")) for row in questioned),
        "contradicted": sorted(str(row.get("pattern_id", "")) for row in contradicted),
        "earned_is_not_a_defect": (
            f"{len(kept)} pattern(s) were kept because the product earned them. Removing a pattern "
            "because it is a known pattern is the failure this analysis exists to avoid"
        ),
        "richness_source": str((direction or {}).get("richness_source", "")),
        "richness_problems": problems,
        "restraint_allowed": restraint,
        "anti_slop_does_not_mean_austere": (
            "a direction may intentionally take its richness from the content or the typography. "
            "What is refused is a direction with no named richness source, which compensates with "
            "generic cards, gradients and decoration"
        ),
        "candidate_convergence": _convergence_summary(candidate_directions),
        "failures": problems,
    }


def _convergence_summary(candidates: Sequence[Mapping] | None) -> dict:
    from . import concepts as concepts_module

    return concepts_module.convergence_risk(candidates or ())


def own_slop(direction: Mapping, *, concept_statement: str = "") -> dict:
    """The local attractor toward mediocrity this direction collapses into if executed lazily.

    Named per direction rather than banned globally. The examples the milestone brief
    offers -- editorial becoming cream-and-serif wellness, technical becoming terminal
    cosplay, automotive becoming a neon HUD -- are exactly the right shape: each is a
    *direction's* characteristic failure, not a forbidden aesthetic.
    """
    from . import concepts as concepts_module

    character = " ".join(str(direction.get(key, "")) for key in (
        "concept", "character", "type_character", "interaction_character", "motion_language",
        "source_thing",
    )).lower().replace("_", " ")
    attractors: list[str] = []
    families = {
        "editorial": ("generic cream and serif wellness", "magazine template with no subject"),
        "technical": ("terminal cosplay", "monospace used as a costume rather than for data"),
        "automotive": ("neon HUD with fake speed lines", "motion graphics standing in for speed"),
        "premium saas": ("monochrome cards with a giant sans headline", "restraint used as a substitute for content"),
        "ai": ("purple gradient with sparkle ornament", "generosity signalling where none was earned"),
        "dashboard": ("identical stat cards in a grid", "summary tiles nobody chose"),
        "editorial-media": ("feature-story hero imagery standing in for content",),
    }
    for label, outcomes in families.items():
        if label.replace(" ", "-") in character or label.split()[0] in character.split():
            attractors.extend(outcomes)
    if not attractors:
        markers = sorted({marker for marker in concepts_module.CONCEPT_MARKERS if marker in character})
        if markers:
            attractors.append(
                f"collapsing toward the {markers[0]} treatment that this system reaches for by default"
            )
    return {
        "failure_mode": str(direction.get("own_failure_mode", "")).strip(),
        "derived_attractors": sorted(set(attractors)),
        "concept": str(concept_statement or direction.get("concept", "")),
        "basis": (
            "the direction's own local attractor toward mediocrity. Not a forbidden style: the same "
            "direction executed carefully is the intended outcome, and this names what laziness "
            "produces instead"
        ),
    }


def own_slop_problems(direction: Mapping) -> list[str]:
    """Every direction must know its own failure mode."""
    problems: list[str] = []
    stated = str(direction.get("own_failure_mode", "")).strip()
    derived = own_slop(direction)
    if not stated:
        problems.append(
            "this direction names no failure mode. Ask: if it were executed lazily, what cliché does "
            "it collapse into? A direction that cannot answer has not been examined closely enough "
            "to have an answer"
        )
    elif len(stated.split()) < 4:
        problems.append(
            f"the failure mode {stated!r} is too short to be one. Name the specific treatment this "
            "direction drifts into, not a single adjective"
        )
    elif str(direction.get("own_failure_mode_banned", "")).strip().lower() in ("true", "yes", "1"):
        problems.append(
            "the failure mode was recorded as a prohibition. It is an attractor to stay alert to, "
            "not a style the direction may never approach -- a direction that cannot touch a "
            "cliché without collapsing is brittle in the other direction"
        )
    if not stated and not derived["derived_attractors"]:
        problems.append(
            "no failure mode was stated and none could be derived, so this direction has no known "
            "weakness recorded against it"
        )
    return problems


def assert_patterns_are_not_bans(patterns: Sequence[Mapping]) -> list[str]:
    """Validate the registry itself. Called by the suite, so a future edit cannot quietly ban."""
    problems: list[str] = []
    for pattern in patterns or ():
        problems.extend(f"{pattern.get('pattern_id', '?')}: {item}" for item in pattern_problems(pattern))
        problems.extend(f"{pattern.get('pattern_id', '?')}: {item}" for item in _looks_like_a_ban(pattern))
    return problems


__all__ = [
    "DEFAULT_PATTERN_FIELDS",
    "DESIGN_DEFAULT_PATTERNS",
    "DETECTION_VERDICTS",
    "PATTERNS_BY_ID",
    "UNEXAMINED",
    "adjudicate",
    "anti_slop_report",
    "assert_patterns_are_not_bans",
    "detect",
    "own_slop",
    "own_slop_problems",
    "pattern_problems",
    "registry",
    "unexamined",
]