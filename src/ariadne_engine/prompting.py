"""Prompt audit and the flagged compact transport profile (AR-204 T2).

What is implemented, and what is only audited
---------------------------------------------
Two different things are called "the prompt":

* the **transport scaffolding** - the packet header, the transport notice, the S4B
  worker contract, the repair context. The engine owns this text, its behaviour
  consequence is small, and code already enforces most of what it says. AR-204
  audits it and implements a ``compact_v2`` variant of it behind the
  ``prompt_profile`` flag.
* the **stage prompt blocks** in ``prompts/*.md``. These are the behavioural
  instruction sets a model actually reasons with. AR-204 audits them block by
  block (measured, classified and with the engine rule that now enforces each
  one), but it implements **no** rewrite of them, because a shorter instruction
  set cannot be shown to behave identically without a live model evaluation, and
  AR-204 runs none. :func:`select_prompt_block` returns the original and says so.

The classification vocabulary is the brief's: ``KEEP``, ``REWRITE``, ``MOVE``,
``DELETE``. A block is only classified ``DELETE`` when an engine rule now refuses
the bad outcome mechanically *and* the worker does not need the sentence to choose
the right action; a behavioural instruction that keeps a worker from improvising
is ``KEEP`` even when the engine would catch the result.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .serialization import digest_text

PROMPT_PROFILES = ("legacy", "compact_v2")

CLASSIFICATIONS = ("KEEP", "REWRITE", "MOVE", "DELETE")

TRANSPORT_BLOCK_RULES: tuple[dict, ...] = (
    {
        "block_id": "packet-title",
        "match": "prefix",
        "value": "ARIADNE ",
        "classification": "KEEP",
        "reason": "the worker must know which stage packet it received",
        "enforced_by": "",
    },
    {
        "block_id": "packet-id",
        "match": "prefix",
        "value": "Packet ID:",
        "classification": "KEEP",
        "reason": "the worker contract and the return transport both name this packet",
        "enforced_by": "",
    },
    {
        "block_id": "provider",
        "match": "prefix",
        "value": "Provider:",
        "classification": "MOVE",
        "reason": "provider identity is already in the run state; the worker only needs it when a task pins an identity",
        "enforced_by": "execution.identity_view",
        "compact": "drop",
    },
    {
        "block_id": "prepared-status",
        "match": "prefix",
        "value": "Status:",
        "classification": "KEEP",
        "reason": "the status line is what stops a reader mistaking a prepared packet for a finished stage",
        "enforced_by": "",
    },
    {
        "block_id": "transport-notice",
        "match": "prefix",
        "value": "TRANSPORT NOTICE",
        "classification": "REWRITE",
        "reason": "the two-line notice repeats the same idea; one line carries the same instruction",
        "enforced_by": "",
        "compact": "rewrite",
        "compact_lines": [
            "TRANSPORT NOTICE: generated transport; the named source files remain canonical; do not copy "
            "Ariadne policies or templates into the project.",
        ],
    },
    {
        "block_id": "source-commit",
        "match": "prefix",
        "value": "Ariadne source commit:",
        "classification": "DELETE",
        "reason": "the worker never acts on the Ariadne source commit, it is volatile, and the run records it",
        "enforced_by": "run-state provenance",
        "compact": "drop",
    },
    {
        "block_id": "parent-packet",
        "match": "prefix",
        "value": "Parent packet:",
        "classification": "MOVE",
        "reason": "continuation identity belongs to the transport record; the S4B contract already names the task",
        "enforced_by": "",
        "compact": "drop",
    },
    {
        "block_id": "independence-boundary",
        "match": "prefix",
        "value": "INDEPENDENCE BOUNDARY",
        "classification": "KEEP",
        "reason": "the reviewer must know it is being given an isolated packet, or it will ask for the project",
        "enforced_by": "review.review_problems",
    },
    {
        "block_id": "return-transport-target",
        "match": "prefix",
        "value": "RETURN TRANSPORT TARGET",
        "classification": "KEEP",
        "reason": "the exact return path is transport behaviour the worker must perform",
        "enforced_by": "",
    },
    {
        "block_id": "worker-task-contract",
        "match": "prefix",
        "value": "WORKER TASK CONTRACT",
        "classification": "KEEP",
        "reason": "the contract is the task; every field is acted on",
        "enforced_by": "",
    },
    {
        "block_id": "worker-lifecycle",
        "match": "prefix",
        "value": "Lifecycle:",
        "classification": "KEEP",
        "reason": "the worker needs to know a repair attempt exists and is bounded before it chooses to retry",
        "enforced_by": "policy.repair_allowed",
    },
    {
        "block_id": "independent-validation-reminder",
        "match": "prefix",
        "value": "Ariadne independently validates this result before preparing S5.",
        "classification": "REWRITE",
        "reason": "code enforces the gate; the sentence only needs to tell the worker that a self-report is not acceptance",
        "enforced_by": "policy.gate_problems, verification.create",
        "compact": "replace",
        "compact_lines": [
            "Ariadne validates this result independently; a worker self-report is not acceptance.",
        ],
    },
    {
        "block_id": "stop-and-report",
        "match": "prefix",
        "value": "Stop and report a conflict, invariant risk, dangerous action, or out-of-scope requirement",
        "classification": "KEEP",
        "reason": (
            "the worker must *choose* the blocked path; code can detect the result but not the choice, "
            "so removing this would remove useful behavioural context"
        ),
        "enforced_by": "TRANSPORT.worker_validation_problems",
    },
    {
        "block_id": "repair-context",
        "match": "prefix",
        "value": "REPAIR CONTEXT FROM PRIOR ATTEMPT",
        "classification": "KEEP",
        "reason": "bounded prior-attempt evidence is what makes a repair different from a repeat",
        "enforced_by": "",
    },
    {
        "block_id": "declared-conditionals",
        "match": "prefix",
        "value": "DECLARED CONDITIONAL INPUTS",
        "classification": "KEEP",
        "reason": "the omission record is evidence of what was deliberately not sent",
        "enforced_by": "context.plan",
    },
)
"""Transport-scaffolding audit. ``compact`` is the action the compact profile takes."""


def transport_audit(preamble: str) -> dict:
    """Classify each transport block, with its measured size and share."""
    lines = str(preamble).splitlines()
    total = len(str(preamble).encode("utf-8"))
    rows: list[dict] = []
    matched: set[str] = set()
    for line in lines:
        stripped = line.strip()
        for rule in TRANSPORT_BLOCK_RULES:
            if stripped.startswith(str(rule["value"])):
                matched.add(str(rule["block_id"]))
                block_text = _block_for(lines, line)
                rows.append({
                    "block_id": rule["block_id"],
                    "classification": rule["classification"],
                    "bytes": len(block_text.encode("utf-8")),
                    "share": round(len(block_text.encode("utf-8")) / total, 6) if total else None,
                    "reason": rule["reason"],
                    "enforced_by": rule["enforced_by"],
                    "compact": rule.get("compact", "keep"),
                    "sample": block_text.splitlines()[0][:160] if block_text else "",
                })
                break
    unmatched_bytes = total - sum(row["bytes"] for row in rows)
    return {
        "blocks": rows,
        "classified_bytes": sum(row["bytes"] for row in rows),
        "unclassified_bytes": max(0, unmatched_bytes),
        "total_bytes": total,
        "blocks_seen": len(rows),
        "rules_seen": len(matched),
        "note": "a transport block the audit does not classify is left untouched by the compact profile",
    }


def _block_for(lines: Sequence[str], target: str) -> str:
    index = list(lines).index(target)
    collected = [lines[index]]
    for line in lines[index + 1:]:
        stripped = line.strip()
        if not stripped:
            break
        if any(stripped.startswith(str(rule["value"])) for rule in TRANSPORT_BLOCK_RULES):
            break
        collected.append(line)
    return "\n".join(collected)


def _rule_for_line(line: str) -> dict | None:
    stripped = line.strip()
    for rule in TRANSPORT_BLOCK_RULES:
        if stripped.startswith(str(rule["value"])):
            return rule
    return None


def compact_preamble(preamble: str) -> dict:
    """Apply the compact actions to the transport scaffolding.

    Only blocks whose rule says ``drop`` or ``rewrite`` change; anything the audit
    did not classify is carried through byte-for-byte, and the result records
    exactly which block ids were touched.
    """
    lines = str(preamble).splitlines()
    output: list[str] = []
    applied: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        rule = _rule_for_line(line)
        if rule is None:
            output.append(line)
            index += 1
            continue
        action = str(rule.get("compact", "keep"))
        if action == "drop":
            applied.append(str(rule["block_id"]))
            index += 1
            while index < len(lines) and lines[index].strip() and _rule_for_line(lines[index]) is None:
                index += 1
            continue
        if action in ("rewrite", "replace"):
            applied.append(str(rule["block_id"]))
            output.extend(str(item) for item in rule.get("compact_lines", []))
            index += 1
            while index < len(lines) and lines[index].strip() and _rule_for_line(lines[index]) is None:
                index += 1
            continue
        output.append(line)
        index += 1
    compacted = _collapse_blank_runs(output)
    return {
        "text": compacted,
        "applied": sorted(set(applied)),
        "bytes_before": len(str(preamble).encode("utf-8")),
        "bytes_after": len(compacted.encode("utf-8")),
        "removed_bytes": max(0, len(str(preamble).encode("utf-8")) - len(compacted.encode("utf-8"))),
    }


def _collapse_blank_runs(lines: Iterable[str]) -> str:
    output: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if blank:
                continue
            blank = True
            output.append("")
        else:
            blank = False
            output.append(line)
    return "\n".join(output).strip("\n")


def compact_packet_text(text: str, *, profile: str = "legacy") -> dict:
    """Apply the prompt profile to an assembled packet.

    The transformation touches only the transport scaffolding before the first
    source section; the stage prompt block and every delivered source are carried
    verbatim in both profiles.
    """
    if str(profile) not in PROMPT_PROFILES:
        raise ValueError(f"unsupported prompt profile: {profile!r}")
    value = str(text)
    marker = "\n===== BEGIN "
    split_at = value.find(marker)
    if split_at < 0:
        preamble, rest = value, ""
    else:
        preamble, rest = value[:split_at], value[split_at:]
    if str(profile) == "legacy":
        return {
            "profile": "legacy",
            "text": value,
            "applied": [],
            "bytes_before": len(value.encode("utf-8")),
            "bytes_after": len(value.encode("utf-8")),
            "removed_bytes": 0,
            "sources_touched": False,
        }
    result = compact_preamble(preamble)
    compacted = result["text"] + ("\n" if rest else "") + rest if rest else result["text"]
    return {
        "profile": "compact_v2",
        "text": compacted,
        "applied": result["applied"],
        "bytes_before": len(value.encode("utf-8")),
        "bytes_after": len(compacted.encode("utf-8")),
        "removed_bytes": max(0, len(value.encode("utf-8")) - len(compacted.encode("utf-8"))),
        "sources_touched": bool(rest) and not compacted.endswith(rest),
        "note": "only transport scaffolding changed; the prompt block and every source are verbatim",
    }


# ------------------------------------------------------- stage prompt audit


PROMPT_SECTION_RULES: tuple[tuple[str, str, str], ...] = (
    ("transport", "DELETE", "the transport supplies the return target and the contract; a prompt copy is redundant"),
    ("request", "KEEP", "the request is the task; it is what the stage is answering"),
    ("context", "KEEP", "the context rules decide what the worker may look at"),
    ("rules", "KEEP", "behavioural rules the model must choose to follow"),
    ("output", "KEEP", "the deliverable shape is contract-relevant"),
    ("quality", "KEEP", "quality criteria the worker applies to its own work"),
    ("verification", "REWRITE", "code enforces the gate; the block only needs the behavioural part"),
    ("example", "MOVE", "examples are useful for shape-sensitive stages and unnecessary in others"),
    ("appendix", "MOVE", "reference material is loaded only when the stage needs it"),
)


def prompt_blocks(text: str) -> list[dict]:
    """Split a prompt into heading-level blocks with measured size and digest."""
    lines = str(text).replace("\r\n", "\n").split("\n")
    blocks: list[dict] = []
    current: dict | None = None
    for line in lines:
        if line.startswith("#"):
            if current is not None:
                current["text"] = "\n".join(current.pop("lines")).strip("\n")
                current["bytes"] = len(current["text"].encode("utf-8"))
                current["digest"] = digest_text(current["text"])
                blocks.append(current)
            heading = line.lstrip("#").strip()
            current = {"heading": heading, "level": len(line) - len(line.lstrip("#")), "lines": [line]}
        elif current is not None:
            current["lines"].append(line)
    if current is not None:
        current["text"] = "\n".join(current.pop("lines")).strip("\n")
        current["bytes"] = len(current["text"].encode("utf-8"))
        current["digest"] = digest_text(current["text"])
        blocks.append(current)
    return blocks


def classify_prompt_block(heading: str) -> dict:
    lowered = str(heading).lower()
    for token, classification, reason in PROMPT_SECTION_RULES:
        if token in lowered:
            return {"classification": classification, "reason": reason}
    return {"classification": "KEEP", "reason": "no rule matched; the block is kept and carries no measured cost case"}


def audit_prompt(path: Path, *, root: Path | None = None) -> dict:
    """Audit one stage prompt file. Offline and read-only."""
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    rows = []
    for block in prompt_blocks(text):
        verdict = classify_prompt_block(block["heading"])
        rows.append({
            "heading": block["heading"],
            "level": block["level"],
            "bytes": block["bytes"],
            "digest": block["digest"],
            "classification": verdict["classification"],
            "reason": verdict["reason"],
        })
    total = len(text.encode("utf-8"))
    return {
        "path": str(file.relative_to(root).as_posix()) if root is not None and file.is_relative_to(root) else str(file),
        "bytes": total,
        "blocks": rows,
        "block_count": len(rows),
        "delete_bytes": sum(row["bytes"] for row in rows if row["classification"] == "DELETE"),
        "rewrite_bytes": sum(row["bytes"] for row in rows if row["classification"] == "REWRITE"),
        "move_bytes": sum(row["bytes"] for row in rows if row["classification"] == "MOVE"),
        "keep_bytes": sum(row["bytes"] for row in rows if row["classification"] == "KEEP"),
        "note": "classifications are proposals; no stage prompt was rewritten in AR-204",
    }


def audit_prompt_directory(root: Path, paths: Iterable[str]) -> dict:
    files = [audit_prompt(Path(root) / name, root=Path(root)) for name in paths]
    return {
        "files": files,
        "total_bytes": sum(item["bytes"] for item in files),
        "delete_bytes": sum(item["delete_bytes"] for item in files),
        "rewrite_bytes": sum(item["rewrite_bytes"] for item in files),
        "move_bytes": sum(item["move_bytes"] for item in files),
        "keep_bytes": sum(item["keep_bytes"] for item in files),
    }


def select_prompt_block(path: Path, *, profile: str = "legacy") -> dict:
    """Return the prompt block for a profile.

    ``legacy`` returns the file unchanged. ``compact_v2`` is *not implemented* for
    stage prompt files: a shorter behavioural instruction set cannot be claimed
    equivalent without a live model evaluation, so this refuses to invent one and
    reports why.
    """
    if str(profile) not in PROMPT_PROFILES:
        raise ValueError(f"unsupported prompt profile: {profile!r}")
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if str(profile) == "legacy":
        return {"profile": "legacy", "text": text, "applied": False, "bytes": len(text.encode("utf-8"))}
    return {
        "profile": "compact_v2",
        "text": text,
        "applied": False,
        "reason": (
            "no compact variant is implemented for stage prompt files; a behavioural rewrite requires a "
            "live model evaluation that AR-204 did not run"
        ),
        "bytes": len(text.encode("utf-8")),
    }


__all__ = [
    "PROMPT_PROFILES",
    "CLASSIFICATIONS",
    "TRANSPORT_BLOCK_RULES",
    "PROMPT_SECTION_RULES",
    "transport_audit",
    "compact_preamble",
    "compact_packet_text",
    "prompt_blocks",
    "classify_prompt_block",
    "audit_prompt",
    "audit_prompt_directory",
    "select_prompt_block",
]
