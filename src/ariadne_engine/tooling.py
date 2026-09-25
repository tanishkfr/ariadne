"""Tool-schema economics and capability packs (AR-204 T4).

What "tool" means in Ariadne
----------------------------
Ariadne does not hand a worker a fixed function catalogue. What a stage receives
is a *packet*: the stage prompt, the policy documents and templates it needs, the
skills its route selected, and the capability registries that describe the
adapters available to it. The cost of a tool surface is therefore the cost of
those declarations, and the AR-204 question is which of them must ride on every
request and which can be loaded when the route actually needs them.

This module answers that with evidence:

* :data:`CORE_CAPABILITIES` is the set of capabilities **every** implementation
  stage needs on its first turn — a read of the sources, a search of the project,
  an edit inside the permitted scope, a shell for the declared validation
  commands, and the return-handoff write. Those stay loaded.
* :data:`CAPABILITY_PACKS` groups the rest by the task surface the transport
  already declares (design, research, verification, writing, social, capture).
  A pack is only created where the repository has a real member file or a real
  adapter family behind it; there is deliberately no release pack and no
  deployment pack, because no worker-facing release or deployment capability
  exists yet (release tooling is operator-side and offline).

Safety rules carried from the milestone brief:

* offloading is a *policy* the caller chooses (``efficiency`` config), and the
  default keeps every pack's declarations in the packet;
* a required capability that is not loaded is **refused**, never silently
  skipped — :func:`required_capability_problems` is the guard;
* discovery must be cheap: :func:`discover` is a static listing with no provider
  call, and it is bounded.

Nothing here reads a project or calls a provider; pack sizes are measured from
the repository files the transport would deliver.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from .contracts import ContractError

CORE_PACK = "core"

CAPABILITY_PACKS: dict[str, dict] = {
    "core": {
        "title": "core implementation capabilities",
        "justification": "every implementation stage needs these on its first turn",
        "always_loaded": True,
        "members": [
            {"id": "read", "kind": "capability", "path": "", "note": "read the delivered sources and project files"},
            {"id": "search", "kind": "capability", "path": "", "note": "search the project for the symbols the task names"},
            {"id": "edit", "kind": "capability", "path": "", "note": "edit inside the permitted scope the contract declares"},
            {"id": "shell", "kind": "capability", "path": "", "note": "run the declared validation commands"},
            {"id": "return-handoff", "kind": "capability", "path": "templates/RETURN-HANDOFF.md",
             "note": "write the marked return handoff the engine ingests"},
        ],
    },
    "design": {
        "title": "design direction and rendered evidence",
        "justification": "declared by S3 and by design-characterised tasks; not needed by backend work",
        "always_loaded": False,
        "members": [
            {"id": "design-taste", "kind": "policy", "path": "DESIGN-TASTE.md"},
            {"id": "design-template", "kind": "template", "path": "templates/DESIGN.md"},
            {"id": "design-motion", "kind": "policy", "path": "DESIGN-MOTION.md", "conditional": True},
            {"id": "design-assets", "kind": "policy", "path": "DESIGN-ASSETS.md", "conditional": True},
            {"id": "design-direction-skill", "kind": "skill", "path": "skills/design-direction.md"},
            {"id": "visual-qa-skill", "kind": "skill", "path": "skills/visual-qa.md"},
            {"id": "creative-review-skill", "kind": "skill", "path": "skills/creative-review.md"},
        ],
    },
    "research": {
        "title": "reference and component research",
        "justification": "declared by S2 and by reference-selected design work; the capability registry is only needed when component research is selected",
        "always_loaded": False,
        "members": [
            {"id": "research-policy", "kind": "policy", "path": "RESEARCH-POLICY.md"},
            {"id": "research-template", "kind": "template", "path": "templates/RESEARCH.md"},
            {"id": "reference-analysis-skill", "kind": "skill", "path": "skills/reference-analysis.md", "conditional": True},
            {"id": "component-research-skill", "kind": "skill", "path": "skills/component-research.md", "conditional": True},
            {"id": "capability-registry", "kind": "registry", "path": "references/capabilities.json", "conditional": True},
        ],
    },
    "verification": {
        "title": "QA and independent review",
        "justification": "declared by the S4B contract and the S5 independence boundary",
        "always_loaded": False,
        "members": [
            {"id": "qa-policy", "kind": "policy", "path": "QA-POLICY.md"},
            {"id": "qa-template", "kind": "template", "path": "templates/QA.md"},
            {"id": "return-handoff-template", "kind": "template", "path": "templates/RETURN-HANDOFF.md"},
            {"id": "evaluation-rubrics", "kind": "policy", "path": "EVALUATION-RUBRICS.md"},
            {"id": "visual-qa-skill", "kind": "skill", "path": "skills/visual-qa.md"},
        ],
    },
    "writing": {
        "title": "writing execution",
        "justification": "declared by the writing transport when the intent is not SOCIAL",
        "always_loaded": False,
        "members": [
            {"id": "writing-root", "kind": "skill", "path": "skills/writing.md"},
            {"id": "writing-creative", "kind": "skill", "path": "skills/writing-creative.md", "conditional": True},
            {"id": "writing-academic", "kind": "skill", "path": "skills/writing-academic.md", "conditional": True},
            {"id": "writing-scientific", "kind": "skill", "path": "skills/writing-scientific.md", "conditional": True},
            {"id": "writing-transformation", "kind": "skill", "path": "skills/writing-transformation.md", "conditional": True},
        ],
    },
    "social": {
        "title": "social content strategy",
        "justification": "declared by the SOCIAL writing intent",
        "always_loaded": False,
        "members": [
            {"id": "social-strategy-skill", "kind": "skill", "path": "skills/social-strategy.md"},
        ],
    },
    "capture": {
        "title": "rendered-evidence capture adapters",
        "justification": "the engine has a real capture adapter family (AR-202D); a browser adapter is DECLARED/UNKNOWN, so the pack exists but its members are recorded honestly",
        "always_loaded": False,
        "members": [
            {"id": "offline-fixture-capture", "kind": "adapter", "path": "", "family": "capture",
             "availability": "AVAILABLE", "note": "deterministic local capture used by the benchmark"},
            {"id": "browser-capture", "kind": "adapter", "path": "", "family": "capture",
             "availability": "DECLARED", "note": "declared browser capture; no probe has established it"},
        ],
    },
}
"""Packs justified by the repository's actual surface.

``release``, ``deployment`` and ``browser`` as separate packs are deliberately
absent: release and deployment tooling is operator-side (`scripts/build-release.py`,
`scripts/install-ariadne-skill.py`) and no worker stage declares it, and the
browser surface is one declared capture adapter inside the ``capture`` pack
rather than a pack of its own.
"""

CORE_CAPABILITIES = tuple(
    member["id"] for member in CAPABILITY_PACKS[CORE_PACK]["members"]
)
"""The capabilities every implementation stage needs on its first turn."""


class _PackFileIndex:
    """A tiny size cache: pack sizes are read once per process for a given root."""

    def __init__(self) -> None:
        self._root: Path | None = None
        self._sizes: dict[str, int] = {}
        self._reads = 0

    def size(self, root: Path, relative: str) -> int:
        if self._root != root:
            self._root = root
            self._sizes = {}
        if relative not in self._sizes:
            path = root / relative
            try:
                self._sizes[relative] = int(path.stat().st_size)
            except OSError:
                self._sizes[relative] = 0
            self._reads += 1
        return self._sizes[relative]

    def stats(self) -> dict:
        return {"files_read": self._reads, "cached_entries": len(self._sizes)}


_INDEX = _PackFileIndex()


def pack_members(pack_id: str, *, root: Path | None = None) -> list[dict]:
    """Members of one pack, with measured size when the member has a real file."""
    pack = CAPABILITY_PACKS.get(str(pack_id))
    if pack is None:
        raise ContractError(f"unknown capability pack: {pack_id!r}")
    rows = []
    for member in pack["members"]:
        entry = dict(member)
        path = str(member.get("path", ""))
        if root is not None and path:
            entry["bytes"] = _INDEX.size(Path(root), path)
        entry["pack"] = str(pack_id)
        rows.append(entry)
    return rows


def pack_bytes(pack_id: str, *, root: Path | None = None) -> int:
    """Declared bytes for one pack. Only real files contribute."""
    return sum(int(member.get("bytes", 0)) for member in pack_members(pack_id, root=root))


def pack_sizes(*, root: Path | None = None) -> dict:
    """Schema-size economics across every pack, measured from the repository."""
    sizes = {}
    for pack_id in sorted(CAPABILITY_PACKS):
        members = pack_members(pack_id, root=root)
        sizes[pack_id] = {
            "members": len(members),
            "bytes": sum(int(item.get("bytes", 0)) for item in members),
            "always_loaded": bool(CAPABILITY_PACKS[pack_id].get("always_loaded")),
            "conditional_members": sum(1 for item in members if item.get("conditional")),
        }
    return {
        "root": str(root) if root is not None else "",
        "packs": sizes,
        "core_bytes": sizes.get(CORE_PACK, {}).get("bytes", 0),
        "deferrable_bytes": sum(
            entry["bytes"] for name, entry in sizes.items() if name != CORE_PACK
        ),
        "note": "bytes are measured file sizes; an adapter member with no file contributes zero and says so",
    }


def select_packs(
    *,
    stage: str = "",
    required_capabilities: Sequence[str] = (),
    selected_skills: Sequence[str] = (),
    task_kind: str = "",
) -> dict:
    """Deterministically select the packs a stage needs.

    The selection is a pure function of the declared stage, the characterisation's
    required capabilities and the selected skills. The core pack is always
    selected; every other pack needs a declared reason, which is recorded.
    """
    chosen: dict[str, str] = {CORE_PACK: "always loaded"}
    stage_value = str(stage).upper()
    skills = {str(item) for item in selected_skills}
    required = {str(item) for item in required_capabilities}
    if stage_value == "S3" or task_kind == "design" or "design-direction" in skills:
        chosen["design"] = f"stage {stage_value or '(none)'} declares design direction" if stage_value == "S3" else "the task requires design direction"
    if stage_value == "S2" or "reference-analysis" in skills or "component-research" in skills:
        chosen["research"] = f"stage {stage_value or '(none)'} declares research" if stage_value == "S2" else "a research skill was selected"
    if stage_value == "S5" or task_kind == "verification" or "visual-qa" in skills:
        chosen["verification"] = f"stage {stage_value or '(none)'} declares independent review" if stage_value == "S5" else "the task requires verification"
    if any(skill.startswith("writing") for skill in skills) or task_kind == "writing":
        chosen["writing"] = "a writing skill was selected"
    if "social-strategy" in skills or task_kind == "social":
        chosen["social"] = "the social strategy skill was selected"
    if task_kind in ("design", "verification") and "visual-qa" in skills:
        chosen["capture"] = "rendered evidence is required by the design review"
    for capability in sorted(required):
        if capability in ("rendered-evidence", "capture"):
            chosen.setdefault("capture", f"the task requires {capability}")
        if capability in ("design-direction",):
            chosen.setdefault("design", "the task requires a design direction")
        if capability in ("reference-research",):
            chosen.setdefault("research", "the task requires reference research")
    return {
        "stage": stage_value,
        "packs": sorted(chosen),
        "reasons": {name: chosen[name] for name in sorted(chosen)},
        "deferred": sorted(name for name in CAPABILITY_PACKS if name not in chosen),
        "provider_neutral": True,
        "note": "selection is deterministic and provider-neutral; a deferred pack's declarations are not sent",
    }


def required_capability_problems(required: Sequence[str], loaded: Sequence[str]) -> list[str]:
    """A required capability that is not loaded is refused, never skipped.

    This is the invariant-41 guard: offloading may not hide a capability the task
    needs. A caller that offloads packs must call this before it proceeds.
    """
    loaded_set = {str(item) for item in loaded}
    problems = []
    for capability in required or ():
        name = str(capability)
        if name not in loaded_set:
            problems.append(
                f"the task requires {name!r} but no selected pack provides it; refusing rather than "
                "continuing without a required capability"
            )
    return problems


def loaded_declarations(pack_ids: Sequence[str], *, root: Path | None = None) -> list[dict]:
    rows: list[dict] = []
    for pack_id in pack_ids:
        rows.extend(pack_members(str(pack_id), root=root))
    return rows


def discover(*, root: Path | None = None, profile: str = "legacy") -> dict:
    """A cheap, static listing of the capability surface.

    The model (or the operator) can see that additional capabilities exist
    without loading their declarations. This function calls nothing and reads only
    measured file sizes; it is the discovery half of offloading, and it is
    deliberately small.
    """
    listing = []
    for pack_id in sorted(CAPABILITY_PACKS):
        if pack_id == CORE_PACK:
            continue
        members = pack_members(pack_id, root=root)
        listing.append({
            "pack": pack_id,
            "title": CAPABILITY_PACKS[pack_id]["title"],
            "members": [str(member["id"]) for member in members],
            "bytes_if_loaded": sum(int(member.get("bytes", 0)) for member in members),
        })
    return {
        "profile": str(profile),
        "core_capabilities": list(CORE_CAPABILITIES),
        "additional_packs": listing,
        "note": "static listing; loading a pack costs one packet section, not a provider call",
    }


def schema_economics(rows: Sequence[Mapping]) -> dict:
    """Schema size versus how often a capability was required, called and failed.

    ``rows`` are observations the caller measured, one per pack and task kind:
    ``{"pack", "task_kind", "required", "called", "errors", "bytes"}``. Frequency
    is reported over the rows supplied; a pack with no row stays unmeasured rather
    than assumed to be unused.
    """
    by_pack: dict[str, dict] = {}
    for row in rows or ():
        pack = str(row.get("pack", ""))
        if not pack:
            continue
        entry = by_pack.setdefault(pack, {
            "rows": 0, "tasks": 0, "required": 0, "called": 0, "errors": 0, "bytes": 0,
        })
        entry["rows"] += 1
        entry["tasks"] += 1
        entry["required"] += 1 if row.get("required") else 0
        called = row.get("called")
        entry["called"] += int(called) if isinstance(called, (int, float)) and not isinstance(called, bool) else 0
        errors = row.get("errors")
        entry["errors"] += int(errors) if isinstance(errors, (int, float)) and not isinstance(errors, bool) else 0
        size = row.get("bytes")
        entry["bytes"] = max(entry["bytes"], int(size)) if isinstance(size, (int, float)) and not isinstance(size, bool) else entry["bytes"]
    for entry in by_pack.values():
        entry["required_frequency"] = round(entry["required"] / entry["tasks"], 6) if entry["tasks"] else None
        entry["call_error_rate"] = round(entry["errors"] / entry["called"], 6) if entry["called"] else None
        entry["classification"] = classify_capability(entry)
    return {
        "packs": dict(sorted(by_pack.items())),
        "note": "frequencies are over the observed rows only; an unobserved pack is absent, not zero",
    }


def classify_capability(entry: Mapping) -> str:
    """CORE / PACK / RARE, from the measured requirement frequency."""
    frequency = entry.get("required_frequency")
    if frequency is None:
        return "UNKNOWN"
    if float(frequency) >= 0.8:
        return "CORE"
    if float(frequency) >= 0.2:
        return "PACK"
    return "RARE"


def offload_safety(rows: Sequence[Mapping]) -> dict:
    """Decide whether offloading a pack is safe, from measured evidence (T20).

    A pack is *unsafe* to offload when most relevant tasks need it on the first
    turn, when the model repeatedly calls it while missing, when policy requires it
    for safety, or when discovering it costs more turns than leaving it loaded.
    Unsafe decisions are recorded with the reason; the caller (policy) decides.
    """
    decisions = []
    for row in rows or ():
        pack = str(row.get("pack", ""))
        frequency = row.get("required_frequency")
        errors = row.get("call_error_rate")
        policy_required = bool(row.get("policy_required"))
        discovery_turns = row.get("discovery_turns")
        reasons: list[str] = []
        safe = True
        if isinstance(frequency, (int, float)) and float(frequency) >= 0.5:
            safe = False
            reasons.append(f"required on {float(frequency):.0%} of relevant tasks")
        if isinstance(errors, (int, float)) and float(errors) > 0:
            safe = False
            reasons.append(f"call error rate {float(errors):.0%} indicates repeated discovery failures")
        if policy_required:
            safe = False
            reasons.append("policy requires this capability for safe action")
        if isinstance(discovery_turns, (int, float)) and float(discovery_turns) > 1:
            safe = False
            reasons.append(f"discovering it costs {discovery_turns} turns")
        decisions.append({
            "pack": pack,
            "safe_to_offload": safe,
            "reasons": reasons or ["no measured reason to keep it loaded"],
        })
    return {
        "decisions": decisions,
        "note": "offloading stays behind the efficiency policy; this function only reports the evidence",
    }


__all__ = [
    "CORE_PACK",
    "CAPABILITY_PACKS",
    "CORE_CAPABILITIES",
    "pack_members",
    "pack_bytes",
    "pack_sizes",
    "select_packs",
    "required_capability_problems",
    "loaded_declarations",
    "discover",
    "schema_economics",
    "classify_capability",
    "offload_safety",
]
