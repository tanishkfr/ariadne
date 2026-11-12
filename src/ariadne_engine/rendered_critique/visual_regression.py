"""Controlled visual regression between two rendered evidence sets (2.4C).

The comparison is deliberately narrower than "did it look right":

* both captures must be validated rendered evidence for the same route, state
  and viewport, bound to different source digests;
* the comparison records its threshold, masks and the exact artifact digests;
* a changed region is a *finding for review*, never an approval or a quality
  score;
* masks are allowed only with a recorded reason, because blanking the part of
  the image that changed is how a visual regression tool lies.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .. import contracts
from ..contracts import ContractError
from .. import visual_diff

SCHEMA_VERSION = "ar-24c-visual-regression-1"
COLLECTION = "visual_regressions"
MAX_RECORDS = 2_000


def _capture(manifest: Mapping, *, route: str, state: str, width: int) -> Mapping | None:
    for row in manifest.get("captures") or ():
        if not isinstance(row, Mapping):
            continue
        viewport = row.get("viewport") if isinstance(row.get("viewport"), Mapping) else {}
        if (
            str(row.get("route", "")) == route
            and str(row.get("state", state)) == state
            and int(viewport.get("width", 0) or 0) == width
        ):
            return row
    return None


def _digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(
    *,
    before_manifest: Mapping[str, Any],
    after_manifest: Mapping[str, Any],
    route: str,
    state: str = "default",
    width: int,
    threshold: float = 0.1,
    masks: Sequence[Mapping] = (),
    mask_reason: str = "",
    task_id: str = "",
) -> dict:
    """Compare one capture identity across two evidence sets."""
    before_set = str(before_manifest.get("evidence_set_id", ""))
    after_set = str(after_manifest.get("evidence_set_id", ""))
    if not before_set or not after_set:
        raise ContractError("a visual regression needs two evidence sets with identities")
    if before_set == after_set:
        raise ContractError(
            "a visual regression compares two evidence sets; comparing one set to itself proves nothing"
        )
    before_digest = str(before_manifest.get("render_source_digest", ""))
    after_digest = str(after_manifest.get("render_source_digest", ""))
    if not contracts._is_sha256(before_digest) or not contracts._is_sha256(after_digest):
        raise ContractError("both evidence sets must carry a render source digest")
    if before_digest == after_digest:
        raise ContractError(
            "the two evidence sets describe the same source digest; use the digest-equality check "
            "for re-production, not a regression comparison"
        )
    left = _capture(before_manifest, route=route, state=state, width=int(width))
    right = _capture(after_manifest, route=route, state=state, width=int(width))
    if left is None or right is None:
        raise ContractError(
            f"no validated capture matches route={route!r} state={state!r} width={width} in both sets"
        )
    for label, row in (("before", left), ("after", right)):
        if str((row.get("artifact") or {}).get("state", "")) != "VALID":
            raise ContractError(f"the {label} capture is not a VALID artifact")
        if str((row.get("viewport") or {}).get("width", "")) != str(width):
            raise ContractError(f"the {label} capture does not declare the compared width")
    if masks and not str(mask_reason or "").strip():
        raise ContractError(
            "masks need a recorded reason; a comparison that blanks the changed region without "
            "saying why is not evidence"
        )
    result = visual_diff.compare_files(
        Path(str(left.get("artifact_path", ""))),
        Path(str(right.get("artifact_path", ""))),
        threshold=float(threshold),
        masks=masks,
    )
    record = {
        "schema_version": SCHEMA_VERSION,
        "comparison_id": contracts.new_record_id("vrg"),
        "task_id": str(task_id),
        "route": str(route),
        "state": str(state),
        "viewport": dict(right.get("viewport") or {}),
        "before": {
            "evidence_set_id": before_set,
            "capture_id": str(left.get("capture_id", "")),
            "render_source_digest": before_digest,
            "artifact_sha256": str(left.get("digest", "")),
        },
        "after": {
            "evidence_set_id": after_set,
            "capture_id": str(right.get("capture_id", "")),
            "render_source_digest": after_digest,
            "artifact_sha256": str(right.get("digest", "")),
        },
        "threshold": float(threshold),
        "masks": [dict(item) for item in masks or ()],
        "mask_reason": str(mask_reason or ""),
        "result": result,
        "requires_review": result.get("verdict") == "CHANGED",
        "quality_judgement": "none",
        "authorization_effect": "none",
        "provenance": {
            "created_by": "engine",
            "policy_version": contracts.POLICY_VERSION,
            "basis": "two validated captures at the same route/state/viewport, different source digests",
        },
        "recorded_at": contracts.utc_now(),
    }
    problems = problems_for(record)
    if problems:
        raise ContractError("visual regression record is malformed: " + "; ".join(problems))
    return record


def problems_for(record: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["visual regression is not an object"]
    if str(record.get("schema_version", "")) != SCHEMA_VERSION:
        problems.append("visual regression schema is unsupported")
    if str(record.get("authorization_effect", "none")) != "none":
        problems.append("a visual regression never grants authorization")
    if str(record.get("quality_judgement", "none")) != "none":
        problems.append("a pixel comparison is not a quality judgement")
    for name in ("comparison_id", "route", "state", "recorded_at"):
        if not str(record.get(name, "")).strip():
            problems.append(f"visual regression has no {name}")
    before = record.get("before") if isinstance(record.get("before"), Mapping) else {}
    after = record.get("after") if isinstance(record.get("after"), Mapping) else {}
    if not str(before.get("evidence_set_id", "")) or not str(after.get("evidence_set_id", "")):
        problems.append("visual regression does not name both evidence sets")
    if str(before.get("evidence_set_id", "")) == str(after.get("evidence_set_id", "")):
        problems.append("visual regression compares one evidence set to itself")
    if str(before.get("render_source_digest", "")) == str(after.get("render_source_digest", "")):
        problems.append("visual regression compares two captures of the same source digest")
    result = record.get("result") if isinstance(record.get("result"), Mapping) else {}
    if str(result.get("verdict", "")) not in ("IDENTICAL", "CHANGED", "INCOMPATIBLE"):
        problems.append("visual regression has no supported verdict")
    if result.get("verdict") == "CHANGED" and not record.get("requires_review"):
        problems.append("a changed render must require review")
    if record.get("masks") and not str(record.get("mask_reason", "")).strip():
        problems.append("masked comparison records no reason")
    return list(dict.fromkeys(problems))


def store(state: dict, record: Mapping[str, Any]) -> dict:
    problems = problems_for(record)
    if problems:
        raise ContractError("refusing to store malformed visual regression: " + "; ".join(problems))
    rows = state.setdefault(COLLECTION, [])
    if len(rows) >= MAX_RECORDS:
        raise ContractError(f"{COLLECTION} bound of {MAX_RECORDS} reached; refused, not truncated")
    stored = json.loads(json.dumps(record, sort_keys=True))
    rows.append(stored)
    return stored


def comparisons(state: Mapping[str, Any]) -> list[dict]:
    return [dict(row) for row in (state.get(COLLECTION) or []) if isinstance(row, Mapping)]


def describe(record: Mapping[str, Any]) -> str:
    result = record.get("result") if isinstance(record.get("result"), Mapping) else {}
    return (
        f"{record.get('comparison_id')} {record.get('route')}@{record.get('state')} "
        f"{result.get('verdict')} ({result.get('changed_pixels')} px changed)"
    )
