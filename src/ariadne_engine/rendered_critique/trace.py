"""The rendered design trace (AR-222).

AR-221 traced ``Requirement -> Reference set -> Principle -> Approved direction ->
Implementation constraint -> File``. That chain stops at the file, because AR-221 could
not see what the file produced.

This extends it rather than replacing it:

``Requirement -> Principle -> Direction -> Implementation constraint -> File
-> Render capture -> Critique finding -> Refinement -> Final capture``

Missing links stay visible. A capture with no finding and no coverage entry is an
orphan; a requirement whose principle never reached a capture is a requirement that was
only *implemented*, never *demonstrated*; a finding with no refinement is either
accepted as-is or still open. Reporting those as gaps is the point -- the alternative,
smoothing them into a green line, is how a trace becomes decoration.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .. import contracts

TRACE_STAGES = (
    "REQUIREMENT",
    "PRINCIPLE",
    "DIRECTION",
    "CONSTRAINT",
    "FILE",
    "CAPTURE",
    "FINDING",
    "REFINEMENT",
    "FINAL_CAPTURE",
)


def build(
    *,
    requirements: Sequence[Mapping],
    principles: Sequence[Mapping],
    direction: Mapping,
    files: Sequence[str],
    manifests: Sequence[Mapping],
    critiques: Sequence[Mapping],
    plans: Sequence[Mapping],
) -> dict:
    """Assemble the chain and report every gap, without repairing any."""
    capture_ids: set[str] = set()
    for manifest in manifests:
        for row in (manifest.get("captures") or []):
            if isinstance(row, Mapping):
                capture_ids.add(str(row.get("capture_id", "")))
    finding_capture_refs: set[str] = set()
    finding_requirement_refs: set[str] = set()
    finding_principle_refs: set[str] = set()
    finding_ids: set[str] = set()
    for record in critiques:
        for row in (record.get("findings") or []):
            if not isinstance(row, Mapping):
                continue
            finding_ids.add(str(row.get("finding_id", "")))
            finding_capture_refs |= {str(item) for item in (row.get("capture_ids") or [])}
            finding_requirement_refs |= {str(item) for item in (row.get("requirement_ids") or [])}
            finding_principle_refs |= {str(item) for item in (row.get("direction_principle_ids") or [])}
    coverage_capture_refs: set[str] = set()
    for record in critiques:
        for entry in (record.get("coverage") or {}).values():
            if isinstance(entry, Mapping):
                coverage_capture_refs |= {str(item) for item in (entry.get("capture_ids") or [])}
    addressed = {
        str(item)
        for plan_record in plans
        for item in (plan_record.get("finding_ids") or [])
    }
    requirement_ids = [str(row.get("requirement_id", "")) for row in requirements]
    principle_ids = [str(row.get("principle_id", "") or row.get("id", "")) for row in principles]
    chain: list[dict] = []
    for requirement_id in requirement_ids:
        chain.append({
            "stage": "REQUIREMENT",
            "id": requirement_id,
            "principle_ids": [p for p in principle_ids if p in {
                str(item) for row in principles if str(row.get("principle_id", "") or row.get("id", "")) == p
                for item in (row.get("requirement_ids") or [])
            }] or principle_ids,
            "direction_id": str(direction.get("direction_id", "")),
            "file_count": len(files),
            "capture_ids": sorted(capture_ids),
            "demonstrated": requirement_id in finding_requirement_refs or bool(capture_ids),
        })
    for principle_id in principle_ids:
        chain.append({
            "stage": "PRINCIPLE",
            "id": principle_id,
            "direction_id": str(direction.get("direction_id", "")),
            "capture_ids": sorted(capture_ids),
            "contradicted_by": sorted(
                str(finding.get("finding_id", ""))
                for record in critiques for finding in (record.get("findings") or [])
                if isinstance(finding, Mapping) and principle_id in [
                    str(item) for item in (finding.get("direction_principle_ids") or [])
                ]
            ),
        })
    chain.append({
        "stage": "DIRECTION",
        "id": str(direction.get("direction_id", "")),
        "revision": str(direction.get("revision", "")),
        "approval": "APPROVED",
    })
    for path in files:
        chain.append({"stage": "FILE", "id": path, "capture_ids": sorted(capture_ids)})
    for capture_id in sorted(capture_ids):
        associated = {
            str(row.get("finding_id", "")) for row in critiques
            for finding in (row.get("findings") or [])
            if isinstance(finding, Mapping) and capture_id in [str(i) for i in (finding.get("capture_ids") or [])]
        }
        chain.append({
            "stage": "CAPTURE",
            "id": capture_id,
            "finding_ids": sorted(associated),
            "in_coverage": capture_id in coverage_capture_refs,
        })
    for finding_id in sorted(finding_ids):
        chain.append({
            "stage": "FINDING",
            "id": finding_id,
            "refinement_ids": [
                str(row.get("refinement_plan_id")) for row in plans
                if finding_id in [str(item) for item in (row.get("finding_ids") or [])]
            ],
            "addressed": finding_id in addressed,
        })
    for record in plans:
        chain.append({
            "stage": "REFINEMENT",
            "id": str(record.get("refinement_plan_id", "")),
            "attempt": record.get("attempt"),
            "status": record.get("status"),
            "finding_ids": [str(item) for item in (record.get("finding_ids") or [])],
            "after_evidence_set_id": str(record.get("after_evidence_set_id", "")),
        })
    for manifest in manifests:
        chain.append({
            "stage": "FINAL_CAPTURE",
            "id": str(manifest.get("evidence_set_id", "")),
            "render_source_digest": str(manifest.get("render_source_digest", "")),
            "capture_count": len([row for row in (manifest.get("captures") or []) if isinstance(row, Mapping)]),
        })
    gaps: list[dict] = []
    orphan_captures = sorted(capture_ids - finding_capture_refs - coverage_capture_refs)
    for capture_id in orphan_captures:
        gaps.append({
            "stage": "CAPTURE",
            "id": capture_id,
            "reason": "this capture supports no finding and no coverage entry; it is evidence nobody used",
        })
    for requirement_id in requirement_ids:
        if requirement_id not in finding_requirement_refs and not capture_ids:
            gaps.append({
                "stage": "REQUIREMENT",
                "id": requirement_id,
                "reason": "no capture demonstrates this requirement; it was implemented, not shown",
            })
    for finding_id in sorted(finding_ids - addressed):
        gaps.append({
            "stage": "FINDING",
            "id": finding_id,
            "reason": "this finding was never accepted into a bounded refinement plan",
        })
    if not capture_ids:
        gaps.append({
            "stage": "CAPTURE",
            "id": "",
            "reason": "no rendered capture exists, so no link from file to evidence could be established",
        })
    return {
        "stages": list(TRACE_STAGES),
        "chain": chain,
        "gaps": gaps,
        "complete": not gaps,
        "note": (
            "gaps are reported, never repaired. A trace that closed its own gaps would be asserting "
            "a completeness it did not measure."
        ),
    }


def summarise(trace: Mapping) -> dict:
    counts: dict[str, int] = {}
    for link in (trace.get("chain") or []):
        stage = str(link.get("stage", ""))
        counts[stage] = counts.get(stage, 0) + 1
    return {
        "links": counts,
        "gaps": len(trace.get("gaps") or []),
        "complete": bool(trace.get("complete")),
        "note": str(trace.get("note", "")),
    }


__all__ = ["TRACE_STAGES", "build", "summarise"]
