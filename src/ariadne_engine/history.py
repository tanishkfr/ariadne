"""History economics and evidence-preserving compaction (AR-204 T7).

The rule this module exists to keep
-----------------------------------
Long runs grow a history that is mostly re-delivered context. Compacting it is
sometimes worth doing — but only if the compaction cannot lose the things a
continuation depends on: the current task state, unresolved work, decisions,
authorizations, evidence references, previously failed approaches, the current
revision and the verification state.

So compaction here is:

* **structural, not narrative** - a protected entry is carried verbatim; an
  unprotected entry becomes one deterministic line (kind, turn, source, bytes,
  digest, first line);
* **reversible** - the complete original history is written to a durable artifact
  whose digest is recorded, and :func:`retrieve_history` re-hashes it before
  handing it back;
* **refusable** - a compaction plan that would drop a protected entry, or that
  claims a summary replaced authoritative content, is refused;
* **measured first** - :func:`history_economics` reports growth, duplicates and
  repeated sources before anyone decides to compact.

Compaction stays behind the efficiency policy and is not enabled by default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from . import contracts
from .contracts import ContractError
from .serialization import canonical_json, digest_bytes, digest_text

HISTORY_DIR = "history"
HISTORY_SCHEMA = 1

ENTRY_KINDS = (
    "task_state",
    "unresolved_work",
    "decision",
    "authorization",
    "evidence_ref",
    "failed_approach",
    "revision",
    "verification",
    "tool_output",
    "summary",
    "planning",
    "conversation",
    "handoff",
    "source",
)

PROTECTED_KINDS = (
    "task_state",
    "unresolved_work",
    "decision",
    "authorization",
    "evidence_ref",
    "failed_approach",
    "revision",
    "verification",
)
"""The kinds a compaction may never drop or paraphrase (invariant 44)."""

COMPACTION_POLICIES = ("off", "structured_v1")

_LINE_LIMIT = 120


def entry(
    kind: str,
    text: str,
    *,
    turn: int = 0,
    source: str = "",
    label: str = "",
    referenced: bool = False,
) -> dict:
    """One history entry with a deterministic digest."""
    if str(kind) not in ENTRY_KINDS:
        raise ContractError(f"unknown history entry kind: {kind!r}")
    value = str(text)
    return {
        "kind": str(kind),
        "label": str(label),
        "source": str(source),
        "turn": int(turn),
        "referenced": bool(referenced),
        "bytes": len(value.encode("utf-8")),
        "digest": digest_text(value),
        "text": value,
        "protected": str(kind) in PROTECTED_KINDS,
    }


def history_economics(entries: Sequence[Mapping]) -> dict:
    """Growth, duplication and staleness measurements over a history."""
    rows = [dict(item) for item in entries or () if isinstance(item, Mapping)]
    by_turn: dict[int, int] = {}
    by_kind: dict[str, dict] = {}
    digests: dict[str, list[str]] = {}
    sources: dict[str, int] = {}
    protected_bytes = 0
    total_bytes = 0
    for item in rows:
        size = int(item.get("bytes", 0) or 0)
        total_bytes += size
        by_turn[int(item.get("turn", 0) or 0)] = by_turn.get(int(item.get("turn", 0) or 0), 0) + size
        kind = str(item.get("kind", "unknown"))
        block = by_kind.setdefault(kind, {"entries": 0, "bytes": 0})
        block["entries"] += 1
        block["bytes"] += size
        if item.get("protected"):
            protected_bytes += size
        digest = str(item.get("digest", ""))
        if digest:
            digests.setdefault(digest, []).append(str(item.get("label", "") or item.get("source", "")))
        source = str(item.get("source", ""))
        if source:
            sources[source] = sources.get(source, 0) + size
    duplicate_groups = {digest: labels for digest, labels in digests.items() if len(labels) > 1}
    duplicate_bytes = 0
    for digest, labels in duplicate_groups.items():
        size = next(int(item.get("bytes", 0) or 0) for item in rows if str(item.get("digest", "")) == digest)
        duplicate_bytes += size * (len(labels) - 1)
    repeated_source_bytes = sum(size for source, size in sources.items() if sum(
        1 for item in rows if str(item.get("source", "")) == source) > 1)
    turns = sorted(by_turn)
    return {
        "entries": len(rows),
        "bytes_total": total_bytes,
        "protected_bytes": protected_bytes,
        "unprotected_bytes": max(0, total_bytes - protected_bytes),
        "bytes_by_turn": {str(turn): by_turn[turn] for turn in turns},
        "bytes_by_kind": dict(sorted(by_kind.items())),
        "duplicate_groups": len(duplicate_groups),
        "duplicate_bytes": duplicate_bytes,
        "repeated_source_bytes": repeated_source_bytes,
        "turn_span": [turns[0], turns[-1]] if turns else [],
        "growth_per_turn": [by_turn[turn] for turn in turns],
        "note": (
            "a long history is a measurement, not a verdict: compaction is only justified by the "
            "duplicate and repeated-source shares, and never drops a protected entry"
        ),
    }


def compaction_problems(entries: Sequence[Mapping], plan: Mapping) -> list[str]:
    """Refuse a compaction plan that would lose something it must keep.

    A protected entry may not be omitted, dropped, replaced by a summary, or named
    in the plan's omit list; a plan that names no archive is refused because the
    full history must stay retrievable.
    """
    problems: list[str] = []
    rows = [item for item in entries or () if isinstance(item, Mapping)]
    omit = {str(item) for item in (plan.get("omit") or [])}
    for index, item in enumerate(rows):
        protected = bool(item.get("protected", str(item.get("kind", "")) in PROTECTED_KINDS))
        if not protected:
            continue
        entry_id = str(item.get("entry_id", f"h{index}"))
        decision = str(item.get("decision", "") or "")
        if decision in ("omit", "drop", "summarise", "summarize"):
            problems.append(
                f"the plan would {decision} a protected {item.get('kind')} entry"
            )
        elif entry_id in omit:
            problems.append(f"the plan omits the protected {item.get('kind')} entry {entry_id}")
    if plan.get("summary_replaces_history"):
        problems.append("a summary cannot replace the history; the original must remain retrievable")
    if not plan.get("archive_digest") and not plan.get("archive_path"):
        problems.append("compaction must archive the complete original history before it compacts")
    return problems


def compact(
    root: Path,
    entries: Sequence[Mapping],
    *,
    policy: str = "structured_v1",
    reason: str = "",
) -> dict:
    """Archive the full history, then return a structured active view.

    The archive is written first; if it cannot be written, the compaction is
    refused. Protected entries appear verbatim in the active view, unprotected
    entries appear as one deterministic line each, and exact duplicates are
    marked as such rather than repeated.
    """
    if str(policy) not in COMPACTION_POLICIES or str(policy) == "off":
        raise ContractError(f"compaction policy {policy!r} is not an enabled compaction policy")
    rows = [dict(item) for item in entries or () if isinstance(item, Mapping)]
    archive_bytes = ("\n".join(canonical_json(row) for row in rows) + "\n").encode("utf-8")
    archive_digest = digest_bytes(archive_bytes)
    target_dir = Path(root) / HISTORY_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    archive_path = target_dir / f"{archive_digest}.jsonl"
    if not archive_path.is_file():
        archive_path.write_bytes(archive_bytes)
    active: list[dict] = []
    omitted: list[dict] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        entry_id = f"h{index}"
        digest = str(row.get("digest", ""))
        record = {
            "entry_id": entry_id,
            "kind": str(row.get("kind", "")),
            "label": str(row.get("label", "")),
            "source": str(row.get("source", "")),
            "turn": int(row.get("turn", 0) or 0),
            "bytes": int(row.get("bytes", 0) or 0),
            "digest": digest,
            "protected": bool(row.get("protected", str(row.get("kind", "")) in PROTECTED_KINDS)),
        }
        if digest and digest in seen and not record["protected"]:
            record["duplicate_of_digest"] = digest
            omitted.append({**record, "compaction": "duplicate"})
            continue
        if digest:
            seen.add(digest)
        if record["protected"]:
            record["text"] = str(row.get("text", ""))
            record["compaction"] = "verbatim-protected"
        else:
            text = str(row.get("text", ""))
            first_line = text.splitlines()[0][:_LINE_LIMIT] if text.splitlines() else ""
            record["first_line"] = first_line
            record["compaction"] = "structured"
            omitted.append({**record, "compaction": "structured"})
        active.append(record)
    protected = sum(1 for row in active if row["protected"])
    result = {
        "schema_version": HISTORY_SCHEMA,
        "policy": str(policy),
        "reason": str(reason),
        "entries": len(rows),
        "active_entries": len(active),
        "protected_entries": protected,
        "structured_entries": len(active) - protected,
        "duplicates_omitted": sum(1 for row in omitted if row.get("compaction") == "duplicate"),
        "archive_path": str(archive_path),
        "archive_digest": archive_digest,
        "archive_bytes": len(archive_bytes),
        "active": active,
        "omitted": omitted,
        "recorded_at": contracts.utc_now(),
        "note": (
            "protected entries are carried verbatim; every other entry keeps its digest and first line; "
            "the complete original is retrievable from the archive"
        ),
    }
    problems = compaction_problems(rows, {
        "omit": [row["entry_id"] for row in omitted],
        "archive_digest": archive_digest,
        "archive_path": str(archive_path),
    })
    if problems:
        raise ContractError("compaction plan is unsafe: " + "; ".join(problems))
    return result


def retrieve_history(result: Mapping) -> dict:
    """Return the complete original history, refusing a changed archive."""
    path = str(result.get("archive_path", ""))
    expected = str(result.get("archive_digest", ""))
    if not path:
        return {"ok": False, "problems": ["the compaction record names no archive"], "entries": []}
    file = Path(path)
    if not file.is_file():
        return {"ok": False, "problems": [f"the history archive is missing: {path}"], "entries": []}
    import json

    raw = file.read_bytes()
    actual = digest_bytes(raw)
    if actual != expected:
        return {
            "ok": False,
            "problems": [f"the history archive digest changed: recorded {expected}, found {actual}"],
            "entries": [],
        }
    entries = []
    for line in raw.decode("utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return {"ok": True, "problems": [], "entries": entries, "sha256": actual, "bytes": len(raw)}


def render_active(result: Mapping) -> str:
    """Render the compact active view as the model-facing block."""
    lines = [
        f"CONTEXT COMPACTION ({result.get('policy')})",
        f"{result.get('entries')} history entries compacted to {result.get('active_entries')} "
        f"({result.get('protected_entries')} protected, {result.get('structured_entries')} structured, "
        f"{result.get('duplicates_omitted')} duplicates omitted).",
        f"Complete original archived at {result.get('archive_path')} "
        f"(sha256 {result.get('archive_digest')}); retrieve it if you need the full text.",
        "",
    ]
    for row in result.get("active") or []:
        if row.get("protected"):
            lines.extend([
                f"[{row.get('kind')} | turn {row.get('turn')} | protected | {row.get('entry_id')}]",
                str(row.get("text", "")),
                "",
            ])
        else:
            lines.append(
                f"[{row.get('kind')} | turn {row.get('turn')} | {row.get('bytes')} bytes | "
                f"{row.get('digest', '')[:12]}] {row.get('first_line', '')}"
            )
    for row in result.get("omitted") or []:
        if row.get("compaction") == "duplicate":
            lines.append(
                f"[duplicate of {row.get('duplicate_of_digest', '')[:12]} | {row.get('kind')} | "
                f"{row.get('bytes')} bytes] omitted from the active view"
            )
    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "HISTORY_DIR",
    "HISTORY_SCHEMA",
    "ENTRY_KINDS",
    "PROTECTED_KINDS",
    "COMPACTION_POLICIES",
    "entry",
    "history_economics",
    "compaction_problems",
    "compact",
    "retrieve_history",
    "render_active",
]
