"""Minimal Creative Interruption: autonomy until meaning changes (AR-222D).

The product principle this module implements:

> **The user describes the outcome. Ariadne researches, explores, designs, builds,
> critiques and verifies.**
>
> **Ariadne should interrupt the human when meaning changes, not when padding changes.**

A tool that asks "should I search Mobbin?" has misread its own job. The user asked for
a dashboard; how Ariadne obtains evidence is not a decision the user is qualified to
make and certainly did not want to make. The tool's competence is precisely that it can
choose a source, a component, a spacing system and a capture plan without being asked.

So the default is **automatic**, and interruption is the exception that has to earn its
place. That inverts the usual shape, where asking is cheap and proceeding is expensive.
Here proceeding is cheap -- padding can be changed -- and asking is expensive: an
interruption spends the user's attention, which is the one resource they cannot get
back.

Three tiers, and the middle one is where the real work is:

```text
AUTOMATIC          routine design, research, implementation and verification
CONDITIONAL        may proceed; must interrupt if meaning changes
HUMAN_REQUIRED     never proceed unattended
```

:data:`AUTONOMOUS_DECISIONS` is the long list. :data:`HUMAN_REQUIRED_DECISIONS` is
short and deliberately so -- every entry is a decision where proceeding *unattended*
would either change what the product means or consume authority the user holds.

The distinction between :data:`MEANING_BEARING_CHANGES` and
:data:`IMPLEMENTATION_CHANGES` is what makes the conditional tier decidable rather than
a matter of taste. "Add 8px of padding" and "make the primary navigation a sidebar
instead of a top bar" are both design changes. One is routine. The other changes the
navigation paradigm, and therefore the meaning, and therefore stops.

Note what is *not* here: no approval for component choice, no gate for reference
selection, no approval for a bounded repair, and no second gate after G1D for ordinary
refinement. The interruption budget is not generous; it is spent.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from ...contracts import ContractError

AUTONOMOUS_DECISIONS = (
    "reference selection",
    "concept exploration",
    "candidate divergence",
    "component choice",
    "component reuse decision",
    "spacing",
    "type candidate evaluation",
    "colour candidate evaluation",
    "source provider choice",
    "source transport choice",
    "capture planning",
    "capture budget",
    "routine critique",
    "bounded repair within an approved direction",
    "re-render and re-review",
    "implementation mechanics",
    "responsive mechanics",
    "hierarchy strength within an approved direction",
    "motion detail within an approved intent",
    "test fixture and demo content selection",
    "empty/loading/error state wording",
    "internal candidate evaluation",
    "recommendation of one direction",
)
"""Decisions Ariadne makes without asking.

The list is long on purpose. Everything here is reversible within an approved
direction, reversible in the sense that undoing it costs nothing the user has to spend
attention on. The question for each is not "is this risky" but "does proceeding without
asking cost the user anything they cannot recover".
"""

HUMAN_REQUIRED_DECISIONS = (
    "G1D design-direction approval",
    "meaningful direction revision",
    "conflicting product intent",
    "protected authorization",
    "paid capability where approval is required",
    "final acceptance where policy requires it",
    "a critique implying a new design direction rather than a repair",
)
"""Decisions that stop the run.

Each is a case where proceeding unattended would either change what the product means
or exercise authority the user holds. The list is deliberately short: every entry costs
a real interruption, so an entry that could have been a routine decision is a bug.
"""

MEANING_BEARING_CHANGES = (
    "product meaning",
    "brand identity",
    "primary creative metaphor",
    "navigation paradigm when direction-bound",
    "major visual language",
    "approved interaction model",
)
"""Changes that stop the run regardless of who proposed them.

These alter what the thing *is*. An implementation that quietly swaps the primary
creative metaphor has made a design decision, not an implementation decision, and the
human who approved the metaphor is the only one who can replace it.
"""

IMPLEMENTATION_CHANGES = (
    "padding",
    "component implementation",
    "responsive mechanics",
    "hierarchy strength",
    "existing approved motion details",
    "copy inside an approved register",
    "icon choice",
    "spacing scale selection",
)
"""Changes Ariadne makes freely inside an approved direction.

The second list exists to make the first one meaningful. Without a stated boundary,
"autonomy until meaning changes" is unfalsifiable -- everything can be called a meaning
change, and the policy silently becomes "ask the user about everything".
"""

INTERRUPTION_TIERS = ("AUTOMATIC", "CONDITIONAL", "HUMAN_REQUIRED")

DIRECTION_APPROVAL_GATE = "G1D"
"""The one meaningful creative interruption.

Kept as the real engine gate rather than a new mechanism: the point is that a user
approving a direction through the existing ``G1D`` boundary is the same act as before,
not a parallel process that could drift from it.
"""

DECLINE_REASONS = (
    "violates project identity",
    "reintroduces a deliberately avoided default",
    "contradicts an approved direction",
    "undoes its own prior requirement without evidence",
    "breaks accessibility",
    "exceeds approved scope",
    "requires direction revision",
)
"""Why a recommendation may be declined.

Recorded rather than silently ignored, because a silently-ignored reviewer request looks
exactly like a reviewer request that was never made -- and the next round produces it
again, with the same reasoning, in a loop.
"""


MEANING_CHANGE_CUES = {
    "product meaning": (
        "what this product is for", "change what the product is", "different product",
        "reposition", "change the audience", "change what users are for",
    ),
    "brand identity": (
        "rebrand", "change the logo", "new brand", "change the brand colour",
        "replace the identity", "change the name",
    ),
    "primary creative metaphor": (
        "change the metaphor", "replace the metaphor", "different metaphor",
        "change the concept", "replace the concept", "abandon the metaphor",
    ),
    "navigation paradigm when direction-bound": (
        "replace the navigation", "swap the navigation", "different navigation",
        "navigation paradigm", "replace the top navigation", "remove the sidebar",
        "sidebar instead of", "instead of tabs", "instead of a sidebar",
        "replace the nav",
    ),
    "major visual language": (
        "change the visual language", "new visual language", "completely redesign",
        "new art direction", "replace the aesthetic", "change the aesthetic",
        "start over visually", "from scratch visually",
    ),
    "approved interaction model": (
        "change the interaction model", "replace the interaction", "different interaction model",
        "change the gesture", "replace the gesture", "remove drag", "replace drag",
    ),
}
"""Structural cues for meaning-bearing changes, keyed by which kind of meaning.

Matching only the phrase "navigation paradigm" would catch a policy document and no
proposal ever. The cue that actually occurs in a real request is *"replace the top
navigation with a persistent sidebar"* -- so the policy has to recognise the shape of
the change, not the wording of the principle. Without this the policy is unfalsifiable
in the dangerous direction: it reads as protective and never fires.
"""


MEANING_NOUNS = {
    "product meaning": (
        "product", "purpose", "audience", "use case", "job to be done", "what it is for",
    ),
    "brand identity": ("brand", "logo", "identity", "wordmark", "name"),
    "primary creative metaphor": (
        "metaphor", "concept", "idea", "premise", "framing", "art direction premise",
    ),
    "navigation paradigm when direction-bound": (
        "navigation", "nav", "sidebar", "top bar", "topbar", "menu structure", "tabs",
        "information architecture",
    ),
    "major visual language": (
        "visual language", "art direction", "aesthetic", "look", "style", "design language",
        "design system", "visual identity",
    ),
    "approved interaction model": (
        "interaction model", "interaction", "gesture", "input model", "control scheme",
        "navigation model", "manipulation", "drag", "swipe", "tap", "pointer",
    ),
}
"""The nouns whose *replacement* changes what the product is.

Paired with :data:`REPLACEMENT_VERBS`. A request reads "swap X to Y", "replace X with
Y", "Y instead of X" -- and the second half names the noun directly, so the noun alone
is not enough: "add a menu to the sidebar" mentions a navigation noun and changes no
paradigm. What matters is that the noun is being *replaced*, which is the verb's job.
"""

REPLACEMENT_VERBS = (
    "replace", "swap", "change", "different", "instead of", "rather than", "move away from",
    "abandon", "drop", "drop the", "instead", "remove the", "no longer",
)
"""Verbs that turn a noun mention into a paradigm change.

``different`` and ``instead`` are included because they are how requests are actually
phrased -- "a completely different visual language", "drag instead of tap" -- and a
policy that only fires on "replace" protects nothing.
"""


def meaning_triggers(change: str) -> list[str]:
    """Which kinds of meaning a proposed change would alter.

    Structural rather than phrase-matched: a noun from :data:`MEANING_NOUNS` appearing
    near a verb from :data:`REPLACEMENT_VERBS` within a short window. Both halves are
    necessary -- a noun alone is a mention, a verb alone says nothing about what.
    """
    import re

    text = " ".join(str(change or "").lower().replace("_", " ").split())
    if not text:
        return []
    found: list[str] = []
    for meaning, cues in MEANING_CHANGE_CUES.items():
        if meaning in text or meaning.replace(" ", "-") in text:
            found.append(meaning)
            continue
        if any(cue in text for cue in cues):
            found.append(meaning)
            continue
        nouns = MEANING_NOUNS.get(meaning, ())
        for noun in nouns:
            if _replaced(text, noun):
                found.append(meaning)
                break
    return sorted(set(found))


def _replaced(text: str, noun: str) -> bool:
    """Whether ``noun`` is being replaced, rather than merely mentioned.

    Both halves are mandatory. An earlier version made the verb groups optional, which
    made every bare mention of "design system" a meaning change -- so the question
    *"which design system should I use"* was classified as an interruption. The brief is
    explicit that the user must never be asked that question, and a policy that raises
    it while claiming to prevent it is worse than no policy.
    """
    import re

    for verb in REPLACEMENT_VERBS:
        if re.search(rf"{re.escape(verb)}[^.]{{0,40}}{re.escape(noun)}", text):
            return True
        if re.search(rf"{re.escape(noun)}[^.]{{0,30}}{re.escape(verb)}", text):
            return True
    return False


_STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "into", "with", "for", "that", "when",
    "if", "is", "are", "it", "its", "in", "on", "by", "as", "at", "from", "not", "this",
    "use", "using", "used", "make", "making", "add", "set", "up", "own",
})


ROUTINE_VOCABULARY = frozenset({
    "component", "components", "primitive", "primitives", "registry", "registries", "library",
    "libraries", "adapter", "adapters", "transport", "transports", "provider", "providers",
    "spacing", "padding", "margin", "typeface", "font", "fonts", "colour", "color", "palette",
    "breakpoint", "breakpoints", "viewport", "capture", "captures", "refactor", "rename",
    "implementation", "mechanics", "responsive", "design", "system",
    "typography", "spacing", "density",
})
"""Single terms whose presence marks a routine design-engine decision.

Checked *after* the human-required rules, so a change that mentions a component library
**and** changes the brand is still a brand change. Without this, a request phrased as
"should I use shadcn or 21st.dev" is unrecognised vocabulary -- which would leave the
one question the brief says the user must never be asked as the only one this policy
cannot classify.
"""

ROUTINE_PHRASES = (
    "design system",
    "component library",
    "implementation primitive",
    "reference site",
    "reference source",
    "capture dimension",
    "capture viewport",
    "critique strategy",
    "anti-slop rule",
    "spacing system",
    "colour system",
    "type system",
    "spacing scale",
    "motion library",
    "icon set",
)
"""Multi-word phrases from the brief's own list of things the user must not be asked.

Phrase matching rather than word sets, because the individual words are too common to
classify on their own: "design" and "system" appear in *"change the design system
entirely"*, which **is** a meaning change, and the phrase is what tells the two apart.
"""


def _significant_words(text: str) -> set[str]:
    return {
        word
        for word in "".join(
            character if character.isalnum() else " " for character in str(text).lower()
        ).split()
        if word not in _STOP_WORDS
    }


def tier(decision: str, *, meaning_bearing: bool = False) -> str:
    """Which tier a decision falls in.

    ``meaning_bearing`` is how a caller reports that a *specific proposed change* alters
    meaning. The decision kind alone cannot answer that: "spacing" is automatic normally
    and a meaning change if it is restating the visual language, and the tier follows the
    change, not the category.

    Routine vocabulary is matched on significant words rather than substrings, because a
    real request says "use the 21st.dev accordion component" and not "component choice".
    Matching the phrase exactly would classify the actual sentence as unrecognised, which
    reads as caution and behaves as an interruption waiting to happen.
    """
    name = " ".join(str(decision or "").lower().split())
    words = _significant_words(name)
    if any(item in name for item in ("g1d", "design-direction approval", "direction approval")):
        return "HUMAN_REQUIRED"
    if any(item in name for item in MEANING_BEARING_CHANGES):
        return "HUMAN_REQUIRED"
    if any(item in name for item in ("conflicting", "authorization", "paid", "final acceptance",
                                     "direction revision", "new design direction")):
        return "HUMAN_REQUIRED"
    if meaning_bearing:
        return "HUMAN_REQUIRED"
    if any(item in name for item in IMPLEMENTATION_CHANGES):
        return "AUTOMATIC"
    for item in AUTONOMOUS_DECISIONS:
        # A single distinctive word is enough; two is needed for genuinely vague ones.
        head = _significant_words(item)
        if not head:
            continue
        if len(head) == 1:
            if head & words:
                return "AUTOMATIC"
        elif head <= words:
            return "AUTOMATIC"
    if words & ROUTINE_VOCABULARY:
        return "AUTOMATIC"
    if any(phrase in name for phrase in ROUTINE_PHRASES):
        return "AUTOMATIC"
    return "CONDITIONAL"


def classify(proposed_change: str, *, decision_kind: str = "", meaning_bearing: bool = False) -> dict:
    """Decide whether a proposed change may proceed, and say why.

    The ``CONDITIONAL`` tier is not a shrug. It proceeds automatically unless the change
    is meaning-bearing, and it records which of :data:`MEANING_BEARING_CHANGES` it would
    have to be checked against -- so "it seemed fine" is not available as a reason.
    """
    change = " ".join(str(proposed_change or "").lower().replace("_", " ").split())
    if not change:
        raise ContractError("a change must be described before it can be classified")
    kind = str(decision_kind or "") or change
    resolved = tier(kind, meaning_bearing=meaning_bearing)
    triggered = sorted(set([
        *meaning_triggers(change),
        *meaning_triggers(kind),
        *[item for item in MEANING_BEARING_CHANGES
          if item in change or item.replace(" ", "-") in change],
    ]))
    if resolved == "CONDITIONAL" and triggered:
        resolved = "HUMAN_REQUIRED"
        meaning_bearing = True
    automatic = [
        item for item in IMPLEMENTATION_CHANGES
        if item in change or (kind and item in kind)
    ]
    return {
        "change": str(proposed_change),
        "decision_kind": kind,
        "tier": resolved,
        "interrupts_user": resolved == "HUMAN_REQUIRED",
        "meaning_bearing": bool(meaning_bearing or triggered),
        "meaning_triggers": triggered,
        "autonomy_basis": automatic if resolved == "AUTOMATIC" else [],
        "gate": DIRECTION_APPROVAL_GATE if resolved == "HUMAN_REQUIRED" else "",
        "reason": _reason(resolved, triggered or automatic),
    }


def _reason(resolved: str, triggers: Sequence[str]) -> str:
    if resolved == "AUTOMATIC":
        if triggers:
            return (
                f"this is an ordinary implementation change ({', '.join(triggers)}). It is reversible, "
                "it does not alter meaning, and asking would spend attention on padding"
            )
        return "routine decision inside the approved direction; the user does not need to choose"
    if resolved == "HUMAN_REQUIRED":
        if triggers:
            return (
                f"this change alters {', '.join(triggers)}. Meaning is changing, so a human decides -- "
                "autonomy runs until meaning changes and not past it"
            )
        return "this decision carries authority the user holds, or changes what the product is"
    return (
        "this change is routine unless it alters meaning. It proceeds automatically; if it would "
        "change product meaning, brand identity, the primary metaphor, a direction-bound navigation "
        "paradigm, the major visual language or the approved interaction model, it stops and asks"
    )


CONSEQUENCE_CLASSES = {
    "MEANING": (
        "product meaning", "brand identity", "creative metaphor", "navigation paradigm",
        "visual language", "interaction model", "information architecture",
        "positioning", "voice", "tone",
        # Copy is included deliberately and not narrowly. The AR-223 correction exists
        # because a CONDITIONAL reading could not distinguish "which icon set" from "the
        # onboarding wording", and the second is the same class of consequence as changing
        # the brand: the user wrote the words, so changing them is a decision about meaning
        # regardless of how small the diff looks.
        "copy", "wording", "rewording", "worded", "label", "microcopy", "onboarding",
    ),
    "AUTHORITY": (
        "approve", "authorise", "authorize", "sign-off", "sign off", "accept", "ship",
        "release", "merge", "publish", "grant", "authorization", "authorisation",
    ),
    "PROTECTED_HUMAN_DECISION": (
        "protected", "human approval", "operator decision", "gate", "g1d", "g2", "g3",
    ),
}
"""The consequence classes :func:`risk_sensitive_tier` judges on.

Grouped by *what would have to change* if the engine guessed wrong, not by how the
proposal reads. This is the vocabulary AR-222D lacked: its classifier decided on the tier
a lexical match produced, so ``CONDITIONAL`` meant "we could not tell" and it treated
that uniformly -- escalating some, proceeding on others, with no principle for which.

There is no ``ROUTINE`` entry, and that is deliberate. The low-risk case is the *absence*
of all three: nothing here is named, so the ambiguity is implementation mechanics, which
:data:`IMPLEMENTATION_CHANGES` already describes as reversible and free to make. Adding a
``ROUTINE`` class would need a list of phrases that mean "harmless", and any such list is
either too short to be safe or too long to be worth having.
"""

RISK_CLASSES = ("LOW", "HIGH", "PROTECTED")
"""What a potential consequence means when the tier cannot be decided lexically.

``LOW``   routine implementation ambiguity; bounded autonomy continues
``HIGH``  meaning or authority is at stake; a human decides
``PROTECTED`` a protected decision is at stake, regardless of anything else
"""

_ELEVATED = ("HIGH", "PROTECTED")


def risk_sensitive_tier(
    proposed_change: str,
    *,
    decision_kind: str = "",
    meaning_bearing: bool = False,
    protected: bool = False,
    stakes: str = "LOW",
    confidence: float | None = None,
) -> dict:
    """Re-decide one uncertain classification by what is at stake, not by how it reads.

    **The AR-223 correction.** :func:`classify` returns ``CONDITIONAL`` when it cannot
    place a change, and AR-222D treated that one way for everything. But ``CONDITIONAL``
    covers both *"the icon set for the empty state is a coin flip"* -- routine, reversible,
    and nobody's meaning changes -- and *"this might reword the onboarding copy or change
    the navigation paradigm"*, which is a design decision the engine has no business
    making alone. Same tier, opposite consequences, one rule applied to both.

    So the rule becomes risk-sensitive:

    * ``CONDITIONAL`` **and** the potential consequence crosses meaning, authority or a
      protected human decision -- escalate. Fail toward the question.
    * ``CONDITIONAL`` **and** nothing above is named -- proceed. Bounded autonomy over
      routine implementation ambiguity continues, because escalating every uncertainty
      trains people to dismiss escalations, and a gate that fires always is not a gate.

    ``confidence`` is recorded and **never decisive**. A caller-supplied number cannot
    lower the tier: having a quantity that looks certain is not evidence about what is at
    stake, and a policy that lets confidence reduce escalation has reintroduced through
    the side door the rule this whole family exists to enforce. Confidence is not
    permission.
    """
    change = " ".join(str(proposed_change or "").lower().replace("_", " ").split())
    if not change:
        raise ContractError("a change must be described before it can be classified")
    kind = str(decision_kind or "") or change
    lexical = classify(change, decision_kind=kind, meaning_bearing=meaning_bearing)

    text = f"{change} {kind}".lower()
    matched = sorted({
        risk_class for risk_class, cues in CONSEQUENCE_CLASSES.items()
        if any(cue in text for cue in cues)
    })
    triggers = sorted(set(lexical["meaning_triggers"]))
    elevated_consequences = [
        item for item in matched if item != "PROTECTED_HUMAN_DECISION"
    ]

    risk_class = "LOW"
    if protected or "PROTECTED_HUMAN_DECISION" in matched:
        risk_class = "PROTECTED"
    elif triggers or elevated_consequences or stakes.upper() == "HIGH":
        risk_class = "HIGH"

    uncertain = lexical["tier"] == "CONDITIONAL"
    escalated_by_risk = uncertain and risk_class in _ELEVATED
    if escalated_by_risk:
        lexical = {**lexical, "tier": "HUMAN_REQUIRED", "interrupts_user": True}
    elif risk_class in _ELEVATED:
        # Even a decisive AUTOMATIC cannot survive a named meaning or authority
        # consequence. `classify` already escalates most of these; this catches the rest
        # so the correction is not merely "escalate the uncertain ones".
        lexical = {**lexical, "tier": "HUMAN_REQUIRED", "interrupts_user": True}

    return {
        **lexical,
        "risk_class": risk_class,
        "consequences": matched,
        "uncertain": uncertain,
        "escalated_by_risk": escalated_by_risk,
        "confidence": None if confidence is None else float(confidence),
        "confidence_used": False,
        "reason": _risk_reason(risk_class, escalated_by_risk, triggers, matched),
        "ar223_correction": (
            "an uncertain classification is re-decided by consequence. Meaning, authority and "
            "protected decisions escalate; routine implementation ambiguity proceeds"
        ),
    }


def _risk_reason(
    risk_class: str,
    escalated_by_risk: bool,
    triggers: Sequence[str],
    matched: Sequence[str],
) -> str:
    named = ", ".join(sorted({*triggers, *matched})) or risk_class
    if risk_class == "PROTECTED":
        return (
            f"this touches a protected human decision ({named}). Protected decisions are not "
            "available to bounded autonomy at any confidence"
        )
    if escalated_by_risk:
        return (
            f"this could not be classified lexically and its potential consequence crosses {named}, "
            "so it fails toward escalation rather than silent autonomy"
        )
    if risk_class == "HIGH":
        return f"this alters {named}, which is a design decision rather than an implementation one"
    return (
        "this is an uncertain but routine implementation ambiguity. Nothing about meaning, authority "
        "or a protected decision is at stake, so bounded autonomy continues; escalating every "
        "uncertainty would make escalation meaningless"
    )


def policy() -> dict:
    """The formal policy, as a record a run can carry and a test can assert against."""
    return {
        "policy_id": "minimal-creative-interruption-1",
        "principle": "autonomy until meaning changes",
        "tiers": list(INTERRUPTION_TIERS),
        "automatic": list(AUTONOMOUS_DECISIONS),
        "human_required": list(HUMAN_REQUIRED_DECISIONS),
        "meaning_bearing_changes": list(MEANING_BEARING_CHANGES),
        "implementation_changes": list(IMPLEMENTATION_CHANGES),
        "direction_approval_gate": DIRECTION_APPROVAL_GATE,
        "decline_reasons": list(DECLINE_REASONS),
        "user_operates": False,
        "user_does_not_choose": (
            "reference sites, MCP providers, design systems, fonts, component libraries, spacing "
            "systems, capture dimensions, critique strategy, anti-slop rules, which registry to "
            "search, or which implementation primitive to use"
        ),
        "never_asked": (
            "pick an aesthetic category, choose a provider, choose a component library, choose a font, "
            "or choose cards"
        ),
        "risk_sensitive": {
            "risk_classes": list(RISK_CLASSES),
            "consequence_classes": sorted(CONSEQUENCE_CLASSES),
            "rule": (
                "a classification that cannot be decided lexically is re-decided by consequence: "
                "meaning, authority and protected human decisions escalate; routine implementation "
                "ambiguity proceeds"
            ),
            "confidence": (
                "a caller-supplied confidence is recorded and never lowers a tier. Confidence is "
                "not permission"
            ),
        },
    }


def policy_problems(record: Mapping) -> list[str]:
    """A stored policy must not have quietly become interrupt-on-everything."""
    problems: list[str] = []
    rows = record.get("automatic")
    if not isinstance(rows, list) or len(rows) < len(AUTONOMOUS_DECISIONS) - 4:
        problems.append(
            "the recorded automatic-decision list has shrunk materially. A policy that interrupts "
            "more than it used to is a regression wearing a new list"
        )
    required = record.get("human_required")
    if not isinstance(required, list) or not required:
        problems.append("the recorded policy names no decision that requires a human")
    if str(record.get("direction_approval_gate", "")) != DIRECTION_APPROVAL_GATE:
        problems.append(
            f"the recorded policy names {record.get('direction_approval_gate')!r} as the direction "
            f"gate; the real boundary is {DIRECTION_APPROVAL_GATE}"
        )
    if record.get("user_operates") is not False:
        problems.append(
            "the recorded policy does not assert that the user does not operate the design engine. "
            "Tool choice is Ariadne's job"
        )
    return problems


def assert_single_interruption(record: Mapping) -> list[str]:
    """After G1D, an ordinary run must reach completion without a second interruption.

    The inverse of the usual check. Rather than confirming that a gate exists, this
    confirms that the pipeline *did not need another one* -- which is the property the
    user actually experiences, and the one that a gate-existence test cannot see.
    """
    problems: list[str] = []
    interruptions = record.get("interruptions")
    if not isinstance(interruptions, list):
        problems.append("a run records the interruptions it caused, or explicitly records none")
        return problems
    for entry in interruptions:
        if not isinstance(entry, Mapping):
            continue
        reason = str(entry.get("reason", "")).lower()
        approved = bool(entry.get("after_direction_approval", False))
        if approved and reason in IMPLEMENTATION_CHANGES:
            problems.append(
                f"the run interrupted the user after the direction was approved, to ask about "
                f"{entry.get('reason')!r}. That is a routine decision inside an approved direction"
            )
    approved_interruptions = [
        entry for entry in interruptions
        if isinstance(entry, Mapping) and bool(entry.get("after_direction_approval", False))
    ]
    if len(approved_interruptions) > 2:
        problems.append(
            f"{len(approved_interruptions)} interruptions after G1D. One meaningful creative "
            "interruption is the design; a second one means the engine is asking the user to do its job"
        )
    return problems


__all__ = [
    "AUTONOMOUS_DECISIONS",
    "CONSEQUENCE_CLASSES",
    "DECLINE_REASONS",
    "DIRECTION_APPROVAL_GATE",
    "HUMAN_REQUIRED_DECISIONS",
    "IMPLEMENTATION_CHANGES",
    "INTERRUPTION_TIERS",
    "MEANING_BEARING_CHANGES",
    "RISK_CLASSES",
    "assert_single_interruption",
    "classify",
    "policy",
    "policy_problems",
    "risk_sensitive_tier",
    "tier",
]