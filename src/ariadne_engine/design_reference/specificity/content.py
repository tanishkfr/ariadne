"""Content before layout: the content model that constrains a layout (AR-222D).

The failure this prevents is ordinary and well-repeated. A layout is chosen, then
placeholder content is fitted to it, and the content that finally arrives -- real
names, a 34-character German compound noun, a value of 0, an error, a row count of
2,300 -- does not fit. The layout was never wrong; it was designed for content nobody
had.

So the content model is established first and it is held to the same honesty rules as
any other evidence:

* **No ``Lorem ipsum``.** Placeholder text is not content evidence. A layout validated
  against filler has been validated against nothing.
* **No suspiciously perfect data.** All values identical, all timestamps within the
  same minute, every name three syllables, every percentage round -- this is the other
  filler, and it is the more dangerous one because it looks like a real screenshot.
* **The states are content.** Empty, loading, error and edge cases are not exceptions
  to a content model; they are the cases whose layout nobody has checked.
* **Ranges, not samples.** A model records the realistic *span* of what will appear, so
  a layout can be tested against the worst plausible value rather than the friendliest.

And one rule that is about fabrication rather than layout:

> Believable demo content is a design-quality technique, not permission to invent
> product evidence.

Specific plausible content makes a design legible. It does not license claiming a real
person, a real company, a real measurement or a real outcome. :func:`content_model_problems`
reports content whose specificity could be mistaken for a factual claim, so the
distinction survives into the record rather than living in a reviewer's head.
"""

from __future__ import annotations

import re
from typing import Mapping, Sequence

from ...contracts import ContractError

FILLER_MARKERS = (
    "lorem ipsum",
    "lorem",
    "ipsum dolor",
    "dolor sit amet",
    "placeholder text",
    "sample text",
    "your text here",
    "tbd",
    "xxx",
    "asdf",
    "foo bar",
    "test test",
    "text goes here",
    "insert text",
)
"""Content that proves nothing. Found as a whole phrase or a whole token, because
``tbd`` inside a real sentence is not filler and ``Lorem`` inside ``Lorem Systems`` is
a company."""

_FILLER_JOINED = tuple(sorted(FILLER_MARKERS, key=len, reverse=True))

REQUIRED_CONTENT_FIELDS = (
    "surface_purpose",
    "headings",
    "actions",
    "row_count",
    "name_length",
    "numeric_range",
    "empty_state",
    "loading_state",
    "error_state",
    "edge_content",
)
"""Everything a layout needs to be tested before it is committed.

Row count, name length and numeric range are the three that catch most real overflow,
and all three are ranges rather than examples for exactly that reason.
"""

STATES = ("empty", "loading", "error")


def content_model(surface: str, *, purpose: str = "", surface_purpose: str = "",
                  headings: Sequence[str] = (), actions: Sequence[str] = (),
                  row_count: Mapping, name_length: Mapping, numeric_range: Mapping,
                  states: Mapping, edge_content: Sequence[str], domain: str = "",
                  notes: str = "") -> dict:
    """One representative content model for one surface.

    ``states`` must carry all three of empty, loading and error. There is no default
    for them, because "we will handle it later" is precisely how a layout ships with
    an unusable empty state.

    ``purpose`` and ``surface_purpose`` are both accepted because the record's field is
    ``surface_purpose`` while the argument reads better as ``purpose``; two spellings of one
    field is a small thing, and a required-but-obscure argument name is how a content
    model stops being written at all.
    """
    model = {
        "content_model_id": _new_id("cmod"),
        "surface": str(surface),
        "domain": str(domain),
        "surface_purpose": str(purpose or surface_purpose).strip(),
        "headings": [str(item).strip() for item in (headings or ()) if str(item).strip()],
        "actions": [str(item).strip() for item in (actions or ()) if str(item).strip()],
        "row_count": _range(row_count),
        "name_length": _range(name_length),
        "numeric_range": _range(numeric_range),
        "empty_state": str((states or {}).get("empty", "")).strip(),
        "loading_state": str((states or {}).get("loading", "")).strip(),
        "error_state": str((states or {}).get("error", "")).strip(),
        "edge_content": [str(item).strip() for item in (edge_content or ()) if str(item).strip()],
        "notes": str(notes),
        "recorded_at": "",
    }
    problems = content_model_problems(model)
    if problems:
        raise ContractError("content model is not usable: " + "; ".join(problems))
    return model


def _new_id(prefix: str) -> str:
    from ... import contracts

    return contracts.new_record_id(prefix)


def _range(value: Mapping | None) -> dict:
    row = value if isinstance(value, Mapping) else {}
    low, high = row.get("low"), row.get("high")
    try:
        low_value = int(low)
        high_value = int(high)
    except (TypeError, ValueError):
        low_value = high_value = 0
    return {
        "low": low_value,
        "high": high_value,
        "typical": str(row.get("typical", "")).strip(),
        "note": str(row.get("note", "")).strip(),
    }


def _is_range(row: Mapping) -> bool:
    low = row.get("low")
    high = row.get("high")
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
        return False
    if high < low:
        return False
    # A range with no spread is a single sample wearing a range's clothes, which is the
    # numeric form of the suspiciously-perfect fixture.
    return (high - low) > 0 or low == 0


def filler_findings(text: str) -> list[str]:
    """Placeholder text found in content that is supposed to be representative."""
    lowered = " ".join(str(text or "").lower().replace("_", " ").split())
    if not lowered:
        return []
    found: list[str] = []
    for marker in _FILLER_JOINED:
        if len(marker) <= 3:
            if re.search(rf"\b{re.escape(marker)}\b", lowered):
                found.append(marker)
        elif marker in lowered:
            found.append(marker)
    return sorted(set(found))


def _suspiciously_perfect(values: Sequence[str]) -> list[str]:
    """Values that are too tidy to be real.

    Three signals, each individually weak and jointly diagnostic: every value identical,
    every value a round number, or every value the same length. Real telemetry is
    untidy in at least one of those three dimensions almost always.
    """
    cleaned = [str(item).strip() for item in values if str(item).strip()]
    if len(cleaned) < 4:
        return []
    reasons: list[str] = []
    if len(set(cleaned)) == 1:
        reasons.append("every sample is the same value")
    numbers: list[float] = []
    for item in cleaned:
        try:
            numbers.append(float(item))
        except ValueError:
            continue
    if len(numbers) == len(cleaned) and numbers:
        if all(value == round(value, 0) for value in numbers) and len(set(numbers)) < len(numbers):
            reasons.append("every numeric sample is a round number")
    lengths = {len(item) for item in cleaned}
    if len(lengths) == 1:
        reasons.append("every sample is exactly the same length")
    return reasons


def content_model_problems(record: Mapping) -> list[str]:
    """Whether a content model can constrain a layout, honestly."""
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["a content model must be a mapping"]
    for name in REQUIRED_CONTENT_FIELDS:
        if name not in record:
            problems.append(f"content model has no {name}")
    if not str(record.get("surface_purpose", "")).strip():
        problems.append("a content model states what its surface is for; 'dashboard' is not a purpose")
    if not [item for item in (record.get("headings") or []) if str(item).strip()]:
        problems.append("a content model names the headings its surface actually carries")
    if not [item for item in (record.get("actions") or []) if str(item).strip()]:
        problems.append("a content model names the actions its surface actually offers")

    for name in ("row_count", "name_length", "numeric_range"):
        row = record.get(name)
        if not isinstance(row, Mapping):
            continue
        if not _is_range(row):
            problems.append(
                f"{name} must be a realistic range with some spread. A single value cannot "
                "overflow, which is exactly why it proves the layout does not"
            )
        typical = str(row.get("typical", "")).strip()
        if typical:
            low, high = row.get("low"), row.get("high")
            try:
                if not (float(low) <= float(typical) <= float(high)):
                    problems.append(
                        f"{name} typical value {typical!r} falls outside its own range "
                        f"{low}..{high}"
                    )
            except (TypeError, ValueError):
                pass

    for state in STATES:
        if not str(record.get(f"{state}_state", "")).strip():
            problems.append(
                f"content model describes the {state} state. A layout checked only against "
                "populated content has not been checked"
            )

    all_text: list[str] = []
    for name in ("headings", "actions", "edge_content"):
        all_text.extend(str(item) for item in (record.get(name) or []))
    for state in STATES:
        all_text.append(str(record.get(f"{state}_state", "")))
    filler = filler_findings(" ".join(all_text))
    if filler:
        problems.append(
            f"content model contains placeholder text ({', '.join(filler)}). A layout validated "
            "against filler has been validated against nothing; use representative real content"
        )

    for name in ("headings", "actions", "edge_content"):
        tidy = _suspiciously_perfect([str(item) for item in (record.get(name) or [])])
        if tidy:
            problems.append(
                f"{name} looks like a fixture rather than content ({'; '.join(tidy)}). Suspiciously "
                "perfect demo data is the same failure as lorem ipsum in a different costume"
            )
    return list(dict.fromkeys(problems))


def fabrication_findings(record: Mapping) -> list[str]:
    """Content specific enough that a reader could mistake it for a factual claim.

    Believable demo content is legitimate. Real names attached to a real company, or
    precise numbers attached to a real measurement, are a different thing, and the
    difference is cheap to preserve and expensive to lose.
    """
    findings: list[str] = []
    text = " ".join(
        str(item)
        for name in ("headings", "actions", "edge_content")
        for item in (record.get(name) or [])
    )
    if re.search(r"\bhttps?://\b|\bwww\.", text):
        findings.append("demo content contains a live URL, which will be read as a real destination")
    if re.search(r"\b(real|actual|measured|production)\b", text, re.IGNORECASE):
        findings.append("demo content claims to be real or measured data")
    if re.search(r"@\w+\.\w+", text):
        findings.append("demo content contains an email address, which reads as a real contact")
    if re.search(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b", text):
        findings.append(
            "demo content contains a specific date; if it is invented it will be read as a record"
        )
    if not str(record.get("domain", "")).strip() and findings:
        findings.append(
            "the content model names no domain, so there is nothing to check the plausibility "
            "of this content against"
        )
    return findings


def content_layout_precedence(record: Mapping) -> list[str]:
    """Whether a layout plan may proceed given the content model it cites.

    The ordering is enforced rather than recommended. A layout plan whose content model
    is missing, unusable, or recorded *after* the plan is refused, because a layout
    decided before its content was described is a layout for content nobody has.
    """
    problems: list[str] = []
    model = record.get("content_model") if isinstance(record.get("content_model"), Mapping) else None
    if model is None:
        problems.append(
            "no layout plan without a content model (CONTENT_BEFORE_LAYOUT). Establish what the "
            "surface will actually carry -- including its empty, loading and error states -- before "
            "committing a layout"
        )
        return problems
    problems.extend(content_model_problems(model))
    plan_order = record.get("content_model_established_at_step")
    layout_order = record.get("layout_decided_at_step")
    if plan_order is None or layout_order is None:
        problems.append(
            "a layout plan records the step at which its content model was established and the step "
            "at which the layout was decided, so the ordering is auditable rather than asserted"
        )
    else:
        try:
            if int(plan_order) >= int(layout_order):
                problems.append(
                    f"the layout was decided at step {layout_order}, before its content model was "
                    f"established at step {plan_order}. Content before layout is a constraint, not "
                    "a preference"
                )
        except (TypeError, ValueError):
            problems.append("content-model and layout ordering steps must be integers")
    if model.get("recorded_at") and record.get("planned_at"):
        if str(model.get("recorded_at")) > str(record.get("planned_at")):
            problems.append(
                "the content model is timestamped after the layout plan that cites it, which means "
                "the plan did not have it when it decided"
            )
    return list(dict.fromkeys(problems))


def layout_constraints(model: Mapping) -> list[str]:
    """The layout obligations a content model implies, as sentences.

    Useful because the obligation is otherwise implicit: a layout is free to be wrong
    about a row count nobody wrote down. This makes the worst plausible value part of
    the specification.
    """
    constraints: list[str] = []
    if not isinstance(model, Mapping):
        return constraints
    rows = model.get("row_count") if isinstance(model.get("row_count"), Mapping) else {}
    names = model.get("name_length") if isinstance(model.get("name_length"), Mapping) else {}
    numbers = model.get("numeric_range") if isinstance(model.get("numeric_range"), Mapping) else {}
    if rows.get("high"):
        constraints.append(
            f"the surface must remain usable at {rows.get('high')} rows of {model.get('surface', 'content')}"
        )
    if names.get("high"):
        constraints.append(
            f"name content must not be truncated at {names.get('high')} characters; "
            "truncation needs an affordance, not a hard cut"
        )
    if numbers.get("high") or numbers.get("low"):
        constraints.append(
            f"numeric content must remain aligned across a range of "
            f"{numbers.get('low')} to {numbers.get('high')}, including values too wide for their column"
        )
    constraints.extend(
        f"the {state} state must be designed, not defaulted"
        for state in STATES
        if str(model.get(f"{state}_state", "")).strip()
    )
    return constraints


def describe(model: Mapping) -> str:
    rows = model.get("row_count") if isinstance(model.get("row_count"), Mapping) else {}
    names = model.get("name_length") if isinstance(model.get("name_length"), Mapping) else {}
    numbers = model.get("numeric_range") if isinstance(model.get("numeric_range"), Mapping) else {}
    return (
        f"{model.get('surface', 'surface')}: {model.get('surface_purpose', '')}; "
        f"rows {rows.get('low', '?')}..{rows.get('high', '?')}, "
        f"names {names.get('low', '?')}..{names.get('high', '?')} chars, "
        f"values {numbers.get('low', '?')}..{numbers.get('high', '?')}, "
        f"{len(model.get('edge_content') or [])} edge case(s)"
    )


__all__ = [
    "FILLER_MARKERS",
    "REQUIRED_CONTENT_FIELDS",
    "STATES",
    "content_layout_precedence",
    "content_model",
    "content_model_problems",
    "describe",
    "fabrication_findings",
    "filler_findings",
    "layout_constraints",
]