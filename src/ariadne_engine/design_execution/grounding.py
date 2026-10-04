"""Deciding whether a change in the code is grounded, incidental, or ungrounded.

> **Every material design choice should have a reason.**

An approved plan constrains an implementation, but an implementation also changes
things the plan never mentioned. Some of those changes are correct - the plan cannot
enumerate every 1px correction - and some are an implementation quietly developing
its own opinions. Telling those apart structurally, before review, is what this
module is for.

Three verdicts, and the distinction between the first two is the whole design:

| Verdict | When | Consequence |
|---|---|---|
| ``GROUNDED`` | a material change that a cited constraint required | recorded, traceable |
| ``GROUNDED_INCIDENTAL`` | a change no material category covers | recorded, not questioned |
| ``UNGROUNDED_DESIGN_CHANGE`` | a material change with no basis | surfaced, blocks acceptance |

plus three refusals that are not degrees of the same thing, because they call for
different responses: ``ACCESSIBILITY_REGRESSION``, ``REFERENCE_CLONING`` and
``OUT_OF_SCOPE``.

**What this can and cannot decide.** These are structural detectors over a diff -
literal colour values, ``backdrop-filter``, a removed ``:focus-visible``, a new
``@keyframes`` block. They catch the choices that announce themselves in source. They
do not evaluate taste, cannot judge whether a layout reads well, and cannot prove
that a change looks right; nothing here claims otherwise. Refusing to pretend
otherwise is what keeps the three verdicts worth reading.
"""

from __future__ import annotations

import re
from typing import Mapping, Sequence

from .. import contracts
from ..contracts import ContractError

# --------------------------------------------------------------- materiality

MATERIAL_SIGNALS: dict[str, tuple[tuple[str, str], ...]] = {
    "brand_color": (
        (r"(?<![\w-])#[0-9a-fA-F]{3,8}\b", "a literal colour value"),
        (r"\b(?:rgba?|hsla?)\(\s*[0-9]", "a literal colour function"),
        (r"\boklch\(|\bcolor-mix\(", "a literal colour function"),
    ),
    "type_family": (
        (r"\bfont-family\s*:", "a font-family declaration"),
        (r"\bfontFamily\s*:", "a font-family property"),
        (r"\bfont\s*:", "a font shorthand"),
    ),
    "type_scale": (
        (r"\bfont-size\s*:", "a font-size declaration"),
        (r"\bfontSize\s*:", "a font-size property"),
        (r"\bline-height\s*:", "a line-height declaration"),
        (r"\blineHeight\s*:", "a line-height property"),
        (r"\bletter-spacing\s*:", "a letter-spacing declaration"),
        (r"\bletterSpacing\s*:", "a letter-spacing property"),
        (r"\btype-(?:scale|step)\b", "a type-scale token"),
    ),
    "navigation_structure": (
        (r"<nav\b", "a navigation landmark"),
        (r"role\s*=\s*[\"']navigation[\"']", "a navigation role"),
        (r"\bnav-?(?:item|rail|bar|group)\b", "a navigation component"),
        (r"\bsidebar\b", "a sidebar"),
    ),
    "primary_layout": (
        (r"\bgrid-template-(?:areas|columns|rows)\s*:", "a grid template"),
        (r"\bdisplay\s*:\s*grid\b", "a grid container"),
        (r"\bgrid-(?:cols|rows)\b|\bcol-span-\d", "a grid utility"),
        (r"\bflex-direction\s*:", "a flex direction"),
        (r"\bworkspace-(?:layout|grid|shell)\b", "a workspace layout"),
    ),
    "component_geometry": (
        (r"\bborder-radius\s*:", "a radius declaration"),
        (r"\bborderRadius\s*:", "a radius property"),
        (r"\bmin-(?:width|height)\s*:", "a size constraint"),
        (r"\bmin(?:Width|Height)\s*:", "a size property"),
        (r"\b(?:height|width)\s*:\s*\d+px", "a fixed size"),
        (r"\b(?:height|width)\s*:\s*\d+px", "a fixed size property"),
        (r"\bborder-(?:width|color)\s*:", "a border declaration"),
        (r"\bborder(?:Width|Color)\s*:", "a border property"),
        (r"\bshadow\b|\bbox-shadow\s*:", "a shadow declaration"),
        (r"\b(?:boxShadow|boxShadowColor)\s*:", "a shadow property"),
    ),
    "interaction_model": (
        (r"\bon(?:Click|KeyDown|PointerDown|Change|Input|Submit)\b", "an event handler"),
        (r"\baddEventListener\s*\(", "an event listener"),
        (r"\bdraggable\b|\bdrag(?:Start|End)?\b", "a drag interaction"),
        (r"\bhotkey\b|\bkeybinding\b|\bshortcut\b", "a keyboard interaction"),
        (r":focus-visible\b", "keyboard focus styling"),
        (r"role\s*=\s*[\"']separator[\"']", "a separator role"),
        (r"\btabindex\b", "tab order"),
    ),
    "motion_system": (
        (r"@(?:-webkit-)?keyframes\b", "a keyframes block"),
        (r"\banimation\s*:", "an animation declaration"),
        (r"\btransition\s*:", "a transition declaration"),
        (r"\bprefers-reduced-motion\b", "reduced-motion handling"),
        (r"\bduration-\d|\bease-", "a motion token"),
    ),
    "surface_language": (
        (r"\bbackdrop-filter\s*:", "a backdrop filter (glass)"),
        (r"\bbackdropFilter\s*:", "a backdrop filter (glass)"),
        (r"(?<![\w-])(?:linear|radial|conic)-gradient\s*\(", "a gradient"),
        (r"\bbg-gradient-\d", "a gradient utility"),
        (r"\bbg-(?:white|black|slate|gray|zinc|neutral)-\d{2,3}\b", "a raw palette utility"),
        (r"\bfrosted\b|\bglassmorphism\b", "a glass surface"),
    ),
    "responsive_structure": (
        (r"@(?:media|container)\b", "a media or container query"),
        (r"\b(?:sm|md|lg|xl|2xl):", "a responsive breakpoint utility"),
        (r"\bgrid-cols-\d+\b", "a responsive column count"),
    ),
    "asset_identity": (
        (r"https?://[^\s\"')]+/(?:logo|brand|wordmark|mark)[^\s\"')]*", "an external brand asset"),
        (r"\b(?:linear|vercel|stripe|notion|figma|raycast|discord|github)\.(?:com|app|io)\b",
         "a third-party brand reference"),
        (r"\bfont-family\s*:[^;]*(?:Inter|SF Pro|Helvetica Neue|Segoe UI)\b", "a borrowed brand typeface"),
    ),
}
"""Literal source signatures for the decisions that need grounding.

Grouped by category so the verdict can say *which* material decision was made, not
merely that one was. The patterns are intentionally narrow: a false positive here
rejects a legitimate change on the authority of a regular expression, which is a
worse failure than missing an exotic one.
"""

ACCESSIBILITY_SIGNALS: tuple[tuple[str, str], ...] = (
    (r":focus-visible", "focus-visible styling"),
    (r":focus\b", "focus styling"),
    (r"\baria-[a-z]+", "an ARIA attribute"),
    (r"\brole\s*=", "a semantic role"),
    (r"\btitle\s*=", "an accessible name"),
    (r"\balt\s*=", "alternative text"),
    (r"<label\b|aria-label=|\blabelText\b", "a label or accessible name"),
    (r"\btabindex\b", "tab order"),
    (r"\bprefers-reduced-motion\b", "reduced-motion handling"),
    (r"\bsr-only\b|\bvisually-hidden\b", "a screen-reader-only affordance"),
    (r"<button\b", "a real button element"),
    (r"<label\b", "a real label element"),
)
"""Affordances whose *removal* is a regression regardless of any reference."""

INCIDENTAL_SIGNALS = (
    r"^\s*//", r"^\s*/\*", r"^\s*\*", r"^\s*$", r"^\s*\+", r"^\s*-",
    r"-webkit-appearance\s*:", r"\bappearance\s*:", r"\bpointer-events\s*:",
    r"\bz-index\s*:", r"\bcursor\s*:", r"^\s*\}", r"^\s*\{", r"^\s*\};",
)
"""Line-level signals that a diff line is mechanical normalisation.

These are *supporting* evidence, not proof. A line matching one of them can still
carry a material change in the same hunk, which is why materiality is decided from
the added and removed lines as a set rather than line by line.
"""


def _lines(text: str) -> list[str]:
    return [line.rstrip() for line in str(text).splitlines()]


def material_categories(added: Sequence[str], removed: Sequence[str] = ()) -> dict[str, list[str]]:
    """Which material categories the *added* lines touched, and what triggered them.

    Direction matters, and getting it wrong is the difference between a useful
    detector and a broken one. The question is whether the implementation *introduced*
    an unauthorised design decision, so the categories come from the lines it added.

    Reading removed lines too would report a change that deletes a glass card as a
    ``surface_language`` and ``brand_color`` decision - so the one edit the approved
    direction explicitly asked for would be flagged as the failure the direction was
    written to prevent. Removed categories are still reported, under
    ``removed_categories``, because *what a change took out* is exactly the evidence
    an AVOID treatment produced.

    Lines that name a pattern in order to exclude it are skipped, for the same reason
    :func:`clone_findings` skips them.
    """
    found: dict[str, list[str]] = {}
    for line in added:
        if _is_mention_only(line):
            continue
        for category, signals in MATERIAL_SIGNALS.items():
            if category in found:
                continue
            for pattern, description in signals:
                if re.search(pattern, line):
                    found.setdefault(category, []).append(description)
                    break
    return found


def removed_material_categories(removed: Sequence[str]) -> dict[str, list[str]]:
    """Material categories the change removed, as evidence of compliance."""
    return material_categories(removed)


FOCUS_RING_RE = re.compile(r"outline\s*:\s*(?P<value>[^;}]+)", re.IGNORECASE)
NULL_FOCUS_RING = re.compile(r"outline\s*:\s*(?:none|0|hidden)\b", re.IGNORECASE)


def accessibility_regressions(before: str, after: str) -> list[str]:
    """Affordances present in the file before the change and absent after it.

    Presence is measured over the *whole* of each version, not over the diff. Using
    diff lines would make a moved line look removed and then added, and including the
    removed lines in the "after" set - as a first attempt here did - means nothing
    can ever be lost, so the check silently passed everything. Both files are cheap
    and this is the one check that must not be lenient.

    Focus gets a second test, because presence alone is not enough there. The signal
    ``:focus-visible`` survives when a stylesheet replaces ``outline: 2px solid
    var(--accent)`` with ``outline: none``: the selector remains, the affordance does
    not. Since a nulled focus ring is invisible in review and permanent for keyboard
    users, the weakening is detected directly.

    Accessibility is the one category where an unreported regression is unacceptable.
    """
    def present(lines: Sequence[str]) -> set[str]:
        return {
            description
            for line in lines
            for pattern, description in ACCESSIBILITY_SIGNALS
            if re.search(pattern, line)
        }

    before_lines = _lines(before)
    after_lines = _lines(after)
    lost = present(before_lines) - present(after_lines)
    had_ring = any(
        value.strip() and not NULL_FOCUS_RING.match(f"outline: {value}")
        for line in before_lines for value in FOCUS_RING_RE.findall(line)
    )
    keeps_ring = any(
        value.strip() and not NULL_FOCUS_RING.match(f"outline: {value}")
        for line in after_lines for value in FOCUS_RING_RE.findall(line)
    )
    if had_ring and not keeps_ring:
        lost.add("a visible focus ring (the rule remains but its outline is nulled)")
    return sorted(lost)


def incidental_evidence(added: Sequence[str], removed: Sequence[str] = ()) -> dict:
    """How much of a diff is recognised mechanical normalisation.

    Reported so that ``GROUNDED_INCIDENTAL`` is an evidenced verdict rather than the
    absence of a verdict. "No material category matched" is a weaker statement than
    "12 of 12 changed lines are comment or brace churn", and the second one is what
    makes the answer reviewable.
    """
    def scan(lines: Sequence[str]) -> int:
        total = 0
        for line in lines:
            if not line.strip():
                total += 1
                continue
            if any(re.match(pattern, line) for pattern in INCIDENTAL_SIGNALS):
                total += 1
        return total

    mechanical = scan(added) + scan(removed)
    return {
        "changed_lines": len(added) + len(removed),
        "mechanical_lines": mechanical,
        "substantive_lines": max(0, len(added) + len(removed) - mechanical),
    }


MENTION_ONLY_LINES = (
    r"doesNotMatch", r"does_not_match", r"must not contain", r"must not reintroduce",
    r"forbidden", r"\bnever\b.*\buse\b", r"assert\.not", r"\breject\b", r"\bno longer\b",
)
"""Retained as the readable summary of :data:`NEGATIVE_ASSERTION_PATTERN`.

Kept because the *reason* a line counts as a mention is easier to review as a list of
the phrasings in circulation than as one dense regular expression.
"""


NEGATION_PATTERN = (
    r"\bnot\b|\bnever\b|\bwithout\b|forbid|reject|prohibit|absent|missing|removed|reintroduc"
    r"|\bno\b(?:\s+[\w-]+){0,2}\s*(?:glass|gradient|pill|shadow|glow|hero|card)\b"
)
"""A denial, in any of the forms a source file actually uses one.

``\\bno\\b`` on its own is far too broad - it would match ``.no-blur { backdrop-filter: ...}``
and skip a real violation. It is therefore only read as a denial when one of the
prohibited treatments follows within a couple of words, which covers the phrasing
sources actually use ("keeps no backdrop-filter glass", "no gradient surfaces") without
matching a CSS class that happens to start with ``no-``.
"""

NEGATIVE_ASSERTION_PATTERN = (
    r"doesNotMatch|does_not_match|not\.toContain|not\.toMatch|assert\.not|notMatch|rejects"
)
"""Assertion constructs that name a pattern in order to assert its absence."""

COMMENT_OR_TITLE = re.compile(r"^\s*(?://|/\*|\*)|(?:^|\s)(?:test|it|describe)\s*\(\s*[\"'`]")
"""A comment line or a test/declaration title."""


def _is_mention_only(line: str) -> bool:
    """Whether a line names a forbidden pattern in order to deny it.

    Three separate shapes have to be caught, because three are common:

    * an assertion - ``assert.doesNotMatch(css, /backdrop-filter/)``;
    * a test title - ``test("the stylesheet keeps no backdrop-filter glass")``;
    * a comment explaining the prohibition.

    Skipping these is what stops the detector from flagging the regression test that
    defends the prohibition as the violation the prohibition forbids. The cost is
    under-detection, which is the cheaper error: a missed violation surfaces as a
    review finding, while a false accusation of the project's own test gets the
    detector switched off and takes the prohibition with it.
    """
    text = str(line)
    if re.search(NEGATIVE_ASSERTION_PATTERN, text, re.IGNORECASE):
        return True
    if not COMMENT_OR_TITLE.search(text):
        return False
    return bool(re.search(NEGATION_PATTERN, text, re.IGNORECASE))


def clone_findings(
    before: str, after: str, forbidden_patterns: Sequence[Mapping]
) -> list[dict]:
    """Literal-reference-copying checks against the plan's own prohibitions.

    Two properties make this usable rather than merely noisy.

    **It reports what the change introduced.** A detector that only looks at the
    state *after* the change cannot tell an implementation that reproduces a
    reference from one that deletes it - and the second is exactly what an AVOID
    treatment asks for. Comparing against the prior state is what keeps the
    counter-reference machinery from flagging its own successful execution.

    **It ignores mentions.** A test asserting a pattern is absent contains that
    pattern. See :data:`MENTION_ONLY_LINES`.

    Structural safeguards, not a plagiarism detector, and the record says so. What
    they catch is the specific failure mode the brief names: implementation that
    reaches for the reference's *assets* and *source* rather than its principles - a
    brand logo URL, an external stylesheet, a wholesale vendored block, a reference
    brand's icon set.

    The important property is the one a detector cannot have: a match **records** a
    finding and never silently edits the code away. Silent removal is how a cloning
    attempt becomes invisible instead of refused.
    """
    findings: list[dict] = []
    prior = str(before or "")
    body = str(after or "")
    # Both scans are per line and share one mention rule. An earlier version searched
    # the whole body for plan detectors while scanning line by line for structural
    # ones, so a detector named inside ``assert.doesNotMatch(html, /card-grid/)``
    # escaped the filter that the very next detector in the same list obeyed. Two
    # strategies inside one function is how a detector starts flagging its own
    # regression test on one input shape and not another.
    live_lines = [line for line in body.splitlines() if not _is_mention_only(line)]
    live_body = "\n".join(live_lines)
    for pattern in forbidden_patterns or ():
        if not isinstance(pattern, Mapping):
            continue
        matched = [
            str(detector) for detector in pattern.get("detectors") or []
            if str(detector) in live_body and str(detector) not in prior
        ]
        if not matched:
            continue
        findings.append({
            "pattern_id": str(pattern.get("pattern_id", "")),
            "anti_pattern": str(pattern.get("anti_pattern", "")),
            "reference_id": str(pattern.get("reference_id", "")),
            "detectors_matched": matched,
            "verdict": "REFERENCE_CLONING",
            "reason": str(pattern.get("reason", "")),
        })
    for line in live_lines:
        for pattern, description in (
            (r"<link[^>]+href\s*=\s*[\"']https?://[^\"']+\.css", "an external stylesheet linked wholesale"),
            (r"https?://[^\s\"')]*/(?:logo|logos|wordmark|mark|brand|glyph|icon)/[^\s\"')]*",
             "an external brand asset"),
            (r"https?://[^\s\"')]*\.(?:svg|png|jpg|jpeg|webp|gif)", "an asset served from a third party"),
            (r"/\*\s*(?:Copyright|Source)\s*:\s*(?!this project)", "a pasted third-party source header"),
            (r"@import\s+(?:url\()?[\"']https?://", "an external CSS import"),
            (r"\b(?:linear|vercel|stripe|notion|figma|raycast|discord|github|openai|anthropic)\.(?:com|app|io|dev)\b",
             "a third-party brand domain referenced in the implementation"),
        ):
            match = re.search(pattern, line, re.IGNORECASE)
            if not match:
                continue
            signature = match.group(0)[:120]
            if signature in prior:
                continue
            findings.append({
                "pattern_id": "cloning-structural",
                "anti_pattern": description,
                "reference_id": "",
                "detectors_matched": [signature],
                "verdict": "REFERENCE_CLONING",
                "reason": (
                    "implementation pulled in a reference's assets or source rather than its principles"
                ),
            })
    return findings


def _grounded_result(result: dict, constraints: Sequence[Mapping], why: str) -> dict:
    """Mark the change GROUNDED and attribute it to the constraints that account for it.

    Mutates and returns ``result``, which is the classification dict the caller is
    already building. ``constraint_ids`` is left alone: it is the *declared* set, and
    the trace needs every constraint the implementation said applied. The grounding
    subset is recorded separately, because the difference matters - citing a
    constraint that does not account for the change is provenance padding, and a
    reader who cannot tell the two apart cannot review either.
    """
    result["grounding_constraint_ids"] = sorted({
        str(row.get("constraint_id", "")) for row in constraints
    })
    result["verdict"] = "GROUNDED"
    result["material"] = True
    result["reference_ids"] = sorted({
        str(reference_id)
        for row in constraints
        for reference_id in (row.get("reference_ids") or [])
    })
    result["explanation"] = why + " - " + ", ".join(
        f"{row.get('category')} ({row.get('basis')})" for row in constraints
    )
    return result


def _declared_constraints(
    result: dict, declared_constraint_ids: Sequence[str], known: Mapping[str, Mapping]
) -> list[Mapping] | None:
    """Resolve declared constraint ids against the plan, or mark the claim invalid.

    ``None`` means an id was cited that the plan does not contain. Resolving this
    *before* anything is decided matters: otherwise a fabricated constraint id could
    buy the incidental verdict, and a material change could be declared unremarkable
    simply by citing something that does not exist.
    """
    declared: list[Mapping] = []
    for constraint_id in declared_constraint_ids:
        constraint_row = known.get(str(constraint_id))
        if constraint_row is None:
            result["verdict"] = "UNGROUNDED_DESIGN_CHANGE"
            result["problem"] = (
                f"the change cites implementation constraint {constraint_id}, which the approved plan "
                "does not contain"
            )
            result["explanation"] = (
                "a constraint id is a claim like any other and must name a constraint the plan really "
                "holds. Inventing one is indistinguishable from having no reason at all"
            )
            return None
        declared.append(constraint_row)
    return declared


def _escapes_project(normalised: str) -> bool:
    """Whether a project-relative path reaches outside the project.

    Covers the three shapes, and the third is the one that is easy to forget:
    ``/etc/passwd``, ``../../etc/passwd`` and ``C:/Windows/System32/config``. A
    drive-letter path contains no ``..`` and no leading slash, so a check that only
    looks for those two reports it as project-relative - and a reference that puts
    one in a file path would then redirect a write to a system directory on exactly
    the platform that uses drive letters.
    """
    if normalised.startswith(("/", "\\")):
        return True
    if ".." in normalised.split("/"):
        return True
    return bool(re.match(r"^[A-Za-z]:[\\/]", normalised))


def classify_change(
    *,
    path: str,
    before: str,
    after: str,
    plan: Mapping,
    declared_constraint_ids: Sequence[str] = (),
    declared_reference_ids: Sequence[str] = (),
    declared_treatment: str = "",
) -> dict:
    """Classify one file-level change against the plan that authorised it.

    The classification answers three questions in order: was this path permitted;
    did the change lose an accessibility affordance; did it introduce a material
    design decision, and if so, does a cited constraint account for it?

    ``declared_*`` are the *claims the implementer made*. They are not believed:
    a constraint id only grounds a change if the plan actually contains it, and a
    reference id only if the plan actually bound it. An implementer that invents a
    constraint id is therefore caught by the same check as one that invents an
    aesthetic.
    """
    from . import plan as plan_module

    if not str(path).strip():
        raise ContractError("a change record must name the file it changed")
    normalised = str(path).replace("\\", "/")
    if _escapes_project(normalised):
        return {
            "path": normalised, "verdict": "OUT_OF_SCOPE", "material": False,
            "categories": {}, "constraint_ids": [], "grounding_constraint_ids": [],
        "reference_ids": [], "treatment": "",
            "problem": f"the changed path escapes the project root: {path}",
            "explanation": "a path outside the project is never in scope, whatever the plan says",
        }

    before_lines, after_lines = _lines(before), _lines(after)
    added = [line for line in after_lines if line not in before_lines]
    removed = [line for line in before_lines if line not in after_lines]

    result: dict = {
        "path": normalised,
        "verdict": "GROUNDED_INCIDENTAL",
        "material": False,
        "categories": {},
        "constraint_ids": [],
        "grounding_constraint_ids": [],
        "reference_ids": [],
        "treatment": str(declared_treatment),
        "added_lines": len(added),
        "removed_lines": len(removed),
        "explanation": "",
        "problem": "",
    }

    forbidden = [row for row in plan.get("forbidden_copy_patterns") or [] if isinstance(row, Mapping)]
    clones = clone_findings(before, after, forbidden)
    if clones:
        result["verdict"] = "REFERENCE_CLONING"
        result["material"] = True
        result["categories"] = {"asset_identity": ["a literal reference reproduction"]}
        result["cloning"] = clones
        result["problem"] = (
            "the change reproduces a reference literally rather than implementing its principles: "
            + "; ".join(sorted({str(row.get("anti_pattern", "")) for row in clones}))
        )
        result["explanation"] = (
            "a reference may inform a design; reproducing its assets, source or markup is the "
            "shortcut AR-221 exists to prevent"
        )
        return result

    lost = accessibility_regressions(str(before), str(after))
    if lost:
        result["verdict"] = "ACCESSIBILITY_REGRESSION"
        result["material"] = True
        result["categories"] = {"interaction_model": ["an accessibility affordance was removed"]}
        result["accessibility_lost"] = lost
        result["problem"] = (
            "the change removed " + ", ".join(lost) + "; accessibility is a floor under the design and "
            "no reference preference, however influential, may trade it away"
        )
        result["explanation"] = (
            "removing keyboard access, focus visibility, semantics or labels is not a design choice "
            "an implementation may make"
        )
        return result

    categories = material_categories(added)
    removed_categories = removed_material_categories(removed)
    result["removed_categories"] = removed_categories
    known = plan_module.constraint_index(plan)

    # The declared constraints are validated before anything is decided, because an
    # invented constraint id invalidates the whole claim - including the incidental
    # verdict, which would otherwise become a way to declare a material change
    # unremarkable simply by citing nothing.
    resolved = _declared_constraints(result, declared_constraint_ids, known)
    if resolved is None:
        result["material"] = bool(categories or removed_categories)
        return result
    declared = resolved

    if not categories:
        if removed_categories and declared:
            # A change that takes a material decision *out* of the code is the
            # visible product of an AVOID treatment, not an incidental edit.
            # Calling it incidental would make the counter-reference's effect
            # unreportable, which is the one thing it must never be.
            return _grounded_result(
                result,
                declared,
                (
                    "the change removes "
                    + ", ".join(sorted(removed_categories))
                    + ", which the approved direction required"
                ),
            )
        incidental = incidental_evidence(added, removed)
        result["incidental"] = incidental
        result["constraint_ids"] = sorted({str(row.get("constraint_id", "")) for row in declared})
        result["grounding_constraint_ids"] = []
        result["explanation"] = (
            "no material design category changed, and no constraint required one. Alignment, padding, "
            "whitespace, vendor prefixes and comment edits are the implementation doing its job, and "
            "requiring a rationale for each of them would make the grounded tier meaningless"
            + (
                f"; {incidental['mechanical_lines']} of {len(added) + len(removed)} changed lines are "
                "recognised mechanical normalisation"
                if incidental["mechanical_lines"] else ""
            )
        )
        return result

    result["categories"] = categories
    result["material"] = True
    result["constraint_ids"] = sorted({str(row.get("constraint_id", "")) for row in declared})
    grounding: list[Mapping] = [
        row for row in declared
        if any(
            item in categories
            for item in contracts.CATEGORY_GROUNDS_MATERIAL.get(str(row.get("category", "")), ())
        )
    ]
    if grounding:
        return _grounded_result(result, grounding, "material change accounted for by")

    unknown_reference = [
        str(reference_id) for reference_id in declared_reference_ids
        if str(reference_id) not in {str(row.get("reference_id", "")) for row in plan.get("reference_bindings") or [] if isinstance(row, Mapping)}
    ]
    if unknown_reference:
        result["problem"] = (
            "the change cites reference(s) "
            + ", ".join(unknown_reference)
            + " that the plan never bound to an implementation constraint"
        )
        result["explanation"] = (
            "a reference set member that informed no constraint is not evidence the implementation "
            "rests on, and citing it retroactively is provenance laundering"
        )
    else:
        result["problem"] = (
            "material design change ("
            + ", ".join(f"{category}: {', '.join(reasons)}" for category, reasons in sorted(categories.items()))
            + ") with no approved basis"
        )
        result["explanation"] = (
            "no project identity, requirement, approved direction principle, implementation reference or "
            "engineering constraint in the plan accounts for this decision. That does not make it wrong - "
            "it makes it a decision nobody authorised"
        )
    result["verdict"] = "UNGROUNDED_DESIGN_CHANGE"
    return result


def is_material(*, categories: Mapping[str, Sequence[str]]) -> bool:
    """Whether a category map counts as material."""
    return bool(categories)


__all__ = [
    "ACCESSIBILITY_SIGNALS",
    "INCIDENTAL_SIGNALS",
    "MATERIAL_SIGNALS",
    "accessibility_regressions",
    "classify_change",
    "clone_findings",
    "incidental_evidence",
    "is_material",
    "material_categories",
    "removed_material_categories",
]
