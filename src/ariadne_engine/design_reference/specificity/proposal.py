"""The direction proposal a human actually reads (AR-222D).

Everything upstream in AR-220 to AR-222 is machine-facing: reference sets, principles,
counter-references, capture manifests, digests. All of it necessary and none of it
readable. This module is the narrow waist between that machinery and a person who
typed *"Make me a cool F1 dashboard."*

The constraint that shapes the format:

> **Concise enough for a human to approve.**

A proposal that dumps every principle, provider id and evidence digest has not
translated anything; it has made the user an unpaid reviewer of an internal artifact.
So this is provider-neutral on purpose. No source ids, no adapter names, no transport,
no digests. Those exist in the record underneath; a user approving a direction does not
need to audit how Ariadne found the evidence to approve what the evidence produced.

What survives translation is exactly what a person could disagree with:

```text
name, concept, character
content_strategy, typography_intent, colour_intent, layout_intent, richness_source, motion_intent
key_principles[], deliberately_avoided_defaults[]
preview_refs[]
approval_required
```

and three actions -- **approve**, **adjust**, **show alternatives**. Not a grid of
alternatives up front, because that is the interface that turns a design tool into a
survey, and a survey is work.

The one thing this will not do is shorten *away* the honesty. ``deliberately_avoided_defaults``
is on the proposal because a direction's failure mode is the most useful thing a person
can check in three seconds, and because it commits the system to not later arriving with
the thing it said it would avoid.
"""

from __future__ import annotations

import hashlib
from typing import Mapping, Sequence

from ...contracts import ContractError
from . import defaults as defaults_module
from . import grammar as grammar_module

PROPOSAL_ACTIONS = ("approve", "adjust", "show-alternatives")
"""The three things a person can do with a proposal.

One recommendation, two alternatives on request. Not a grid, and never "pick from all
internal experiments" -- the experiments are ours to run, not the user's to adjudicate.
"""

INTERNAL_ONLY_FIELDS = (
    "source_id",
    "provider_id",
    "adapter_id",
    "transport",
    "reference_id",
    "reference_set_id",
    "render_source_digest",
    "concept_id",
    "recommendation_id",
    "evidence_set_id",
    "direction_revision",
)
"""Never rendered into the user-facing text.

Checked rather than trusted: a future edit that adds a source id to the proposal's
``preview_refs`` would otherwise leak internal provider identity straight into the
interface, and it would read as perfectly reasonable while doing it.
"""

PROPOSAL_SECTIONS = (
    "content_strategy",
    "typography_intent",
    "colour_intent",
    "layout_intent",
    "motion_intent",
)


def proposal(
    direction: Mapping,
    *,
    name: str,
    concept: str,
    character: str,
    content_strategy: str,
    typography_intent: str,
    colour_intent: str,
    layout_intent: str,
    richness_source: str,
    motion_intent: str,
    key_principles: Sequence[str],
    deliberately_avoided_defaults: Sequence[str],
    preview_refs: Sequence[str] = (),
    direction_id: str = "",
    approval_required: bool = True,
    gate: str = "G1D",
) -> dict:
    """Build a provider-neutral proposal derived from an approved-candidate direction."""
    record = {
        "proposal_id": "",
        "direction_id": str(direction_id),
        "name": str(name).strip(),
        "concept": str(concept).strip(),
        "character": str(character).strip(),
        "content_strategy": str(content_strategy).strip(),
        "typography_intent": str(typography_intent).strip(),
        "colour_intent": str(colour_intent).strip(),
        "layout_intent": str(layout_intent).strip(),
        "richness_source": str(richness_source).strip().upper(),
        "motion_intent": str(motion_intent).strip().upper(),
        "key_principles": [str(item).strip() for item in (key_principles or ()) if str(item).strip()],
        "deliberately_avoided_defaults": [
            str(item).strip() for item in (deliberately_avoided_defaults or ()) if str(item).strip()
        ],
        "preview_refs": [str(item) for item in (preview_refs or ())],
        "approval_required": bool(approval_required),
        "gate": str(gate),
        "actions": list(PROPOSAL_ACTIONS),
    }
    problems = proposal_problems(record, direction=direction)
    if problems:
        raise ContractError("direction proposal is not approvable: " + "; ".join(problems))
    from ... import contracts

    record["proposal_id"] = contracts.new_record_id("dpp")
    return record


def proposal_problems(record: Mapping, *, direction: Mapping | None = None) -> list[str]:
    """A proposal must be approvable by a person, and must not leak internal identity."""
    problems: list[str] = []
    if not str(record.get("name", "")).strip():
        problems.append("a proposal is named")
    for field_name in ("concept", "character", *PROPOSAL_SECTIONS):
        if not str(record.get(field_name, "")).strip():
            problems.append(f"a proposal states its {field_name.replace('_', ' ')}")
    if str(record.get("richness_source", "")) not in grammar_module.RICHNESS_SOURCES:
        problems.append(
            f"a proposal names where its visual richness comes from; "
            f"{record.get('richness_source') or 'nothing'} is not a richness source"
        )
    if not [item for item in (record.get("key_principles") or []) if str(item).strip()]:
        problems.append("a proposal carries the principles a person can disagree with")
    if not [item for item in (record.get("deliberately_avoided_defaults") or []) if str(item).strip()]:
        problems.append(
            "a proposal states what it is deliberately avoiding. This is the most checkable part "
            "of the whole proposal and it is what makes the approval meaningful"
        )
    if record.get("approval_required") is not True:
        problems.append(
            "a design direction requires human approval before implementation. This is the one "
            "interruption the method spends"
        )
    if str(record.get("gate", "")) != "G1D":
        problems.append(f"the proposal's approval gate is G1D, not {record.get('gate')!r}")

    text = user_facing_text(record)
    for field_name in INTERNAL_ONLY_FIELDS:
        if field_name in text:
            problems.append(
                f"the user-facing proposal exposes the internal field {field_name!r}. Provider and "
                "source identity stays in the record underneath"
            )
    for entry in record.get("preview_refs") or ():
        if str(entry) and any(token in str(entry) for token in INTERNAL_ONLY_FIELDS):
            problems.append(
                f"a preview reference exposes internal identity: {entry!r}. Previews describe the "
                "design, not how it was researched"
            )
    if direction:
        problems.extend(_consistency_problems(record, direction))
    return list(dict.fromkeys(problems))


def _consistency_problems(record: Mapping, direction: Mapping) -> list[str]:
    """The proposal must not overstate what the direction actually decided."""
    problems: list[str] = []
    direction_richness = str(direction.get("richness_source", "")).strip().upper()
    if direction_richness and direction_richness != str(record.get("richness_source", "")):
        problems.append(
            f"the proposal says the richness source is {record.get('richness_source')!r} but the "
            f"direction recorded {direction_richness!r}. A proposal that disagrees with its own "
            "direction is worse than no proposal"
        )
    own = str(direction.get("own_failure_mode", "")).strip()
    avoided = [str(item).lower() for item in (record.get("deliberately_avoided_defaults") or [])]
    if own and not any(
        token in " ".join(avoided) for token in _significant_words(own)
    ):
        problems.append(
            f"the direction's own failure mode is {own!r} but the proposal's deliberately-avoided "
            "list does not mention it. The proposal must show the person what can go wrong"
        )
    return problems


def _significant_words(text: str) -> list[str]:
    stop = {
        "the", "a", "an", "and", "or", "of", "to", "into", "with", "for", "that", "when",
        "if", "is", "are", "it", "its", "in", "on", "by", "as", "at", "from", "not",
    }
    return [
        word for word in "".join(
            character if character.isalnum() or character.isspace() else " "
            for character in str(text).lower()
        ).split()
        if len(word) > 3 and word not in stop
    ]


def user_facing_text(record: Mapping) -> str:
    """Exactly what the user sees.

    Short by construction. Fixed labels, no internal vocabulary, no evidence trail. The
    ``Avoiding:`` block is placed last on purpose: it is the cheapest possible check on
    whether the system understood the request, and a person who recognises a cliché in
    that list can reject the direction in three seconds without reading the rest.
    """
    lines = [str(record.get("name", "")).strip().upper(), ""]
    concept = str(record.get("concept", "")).strip()
    if concept:
        lines.extend([concept, ""])
    character = str(record.get("character", "")).strip()
    if character:
        lines.extend([character, ""])
    for field_name, label in (
        ("content_strategy", "Content"),
        ("typography_intent", "Hierarchy"),
        ("colour_intent", "Colour"),
        ("layout_intent", "Layout"),
        ("richness_source", "Richness"),
        ("motion_intent", "Motion"),
    ):
        value = str(record.get(field_name, "")).strip()
        if not value:
            continue
        pretty = {
            "REAL_CONTENT": "real content",
            "DATA_VISUALISATION": "data visualisation",
            "TYPOGRAPHY": "typography itself",
            "CONTENT_DENSITY": "content density",
            "PHYSICAL_OBJECT_METAPHOR": "a physical object metaphor",
        }.get(value, value.replace("_", " ").lower())
        lines.append(f"{label}: {pretty}")
    lines.append("")
    principles = [str(item).strip() for item in (record.get("key_principles") or []) if str(item).strip()]
    if principles:
        lines.append("Principles:")
        lines.extend(f"- {item}" for item in principles)
        lines.append("")
    avoided = [
        str(item).strip() for item in (record.get("deliberately_avoided_defaults") or []) if str(item).strip()
    ]
    if avoided:
        lines.append("Avoiding:")
        lines.extend(f"- {item}" for item in avoided)
    return "\n".join(lines).strip()


def approval_request(record: Mapping) -> dict:
    """What a human is asked to approve, and what binds the answer.

    ``proposal_digest`` is over the user-facing text rather than the whole record, so
    the thing a person approved is exactly the thing they were shown. An approval that
    binds a digest nobody read is not an approval.
    """
    from ... import contracts

    text = user_facing_text(record)
    return {
        "proposal_id": str(record.get("proposal_id", "")),
        "direction_id": str(record.get("direction_id", "")),
        "gate": str(record.get("gate", "G1D")),
        "text": text,
        "proposal_digest": _text_digest(text),
        "actions": list(PROPOSAL_ACTIONS),
        "prompt": (
            "Approve direction, adjust, or show alternatives?"
        ),
        "approval_required": bool(record.get("approval_required", True)),
        "note": (
            "the digest covers the text shown to the user, not the underlying record. Approving "
            "binds what was read"
        ),
    }


def _text_digest(text: str) -> str:
    """Digest of exactly the text a human read.

    Hashed locally rather than through :func:`contracts.digest_fields`, which only
    accepts registered approval subject types. This is not an approval of a gated
    subject -- it is a fingerprint of a piece of user-facing text -- and inventing a
    subject type for it would put a proposal on the same footing as a real gated
    record.
    """
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def render_interface(*, proposal_record: Mapping, approval: Mapping | None = None) -> str:
    """The whole user-facing exchange, as it would appear in a terminal."""
    request = approval if approval is not None else approval_request(proposal_record)
    lines = [
        "Ariadne has a recommended direction.",
        "",
        request["text"],
        "",
        request["prompt"],
    ]
    actions = "  ".join(f"[{action}]" for action in (request.get("actions") or ()))
    if actions:
        lines.extend(["", actions])
    lines.append("")
    lines.append(
        "Ariadne chose this itself: the references, the concepts it compared, the type and colour "
        "candidates and the component choices were all decided internally."
    )
    return "\n".join(lines)


def approval_record(record: Mapping, *, identity: str, note: str = "", channel: str = "human-cli") -> dict:
    """The fixture/human approval of a proposal.

    Wraps the real ``G1D`` approval rather than inventing a parallel mechanism: a
    proposal approval that did not go through the gate would be a second, weaker path to
    the same authority, and the weaker path is the one that gets used.
    """
    approver = str(identity or "").strip()
    if not approver:
        raise ContractError("a proposal approval records who approved it")
    from ... import contracts

    request = approval_request(record)
    return {
        "proposal_id": str(record.get("proposal_id", "")),
        "direction_id": str(record.get("direction_id", "")),
        "gate": str(record.get("gate", "G1D")),
        "approver": approver,
        "channel": str(channel),
        "approved_at": contracts.utc_now(),
        "proposal_digest": str(request["proposal_digest"]),
        "approved_text": str(request["text"]),
        "note": str(note),
        "authority": "human",
        "meaning_change": False,
        "basis": (
            "the approval binds the exact text the approver read. It is routed through the real G1D "
            "gate, so it authorises exactly what a direct G1D approval would have"
        ),
    }


def approval_problems(record: Mapping, *, proposal_record: Mapping | None = None) -> list[str]:
    problems: list[str] = []
    if not str(record.get("approver", "")).strip():
        problems.append("a proposal approval records who approved it")
    if str(record.get("authority", "")).lower() != "human":
        problems.append(
            "a design direction is approved by a human. An engine or worker identity approving its "
            "own direction is not an approval"
        )
    if not str(record.get("proposal_digest", "")).strip():
        problems.append("a proposal approval binds the digest of the text that was shown")
    if proposal_record is not None:
        expected = approval_request(proposal_record)["proposal_digest"]
        if str(record.get("proposal_digest", "")) != expected:
            problems.append(
                "the approved digest does not match the current proposal text. Someone approved a "
                "different direction"
            )
    if record.get("meaning_change") not in (False, None):
        problems.append(
            "a proposal approval is not a meaning change. Revising what a direction means requires a "
            "new human decision rather than a re-approval"
        )
    return problems


__all__ = [
    "INTERNAL_ONLY_FIELDS",
    "PROPOSAL_ACTIONS",
    "PROPOSAL_SECTIONS",
    "approval_problems",
    "approval_record",
    "approval_request",
    "proposal",
    "proposal_problems",
    "render_interface",
    "user_facing_text",
]