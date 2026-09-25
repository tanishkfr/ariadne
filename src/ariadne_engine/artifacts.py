"""Large-output externalization with full evidence preserved (AR-204 T6).

The rule this module exists to keep
-----------------------------------
Active context should not carry a 200 KB command log it will never read again.
But the evidence itself must survive: a summary is not the artifact, and a
truncated log is not evidence. So the shape is always

    full output -> durable artifact -> digest + metadata -> short model-facing block

and the full artifact stays readable by verification afterwards.

Three states are explicit, and the threshold that picks between them is measured
rather than invented:

* ``fully_inline`` - small output stays exactly as it was;
* ``inline_excerpt_plus_artifact`` - the model gets a bounded head/tail excerpt and
  a reference to the complete artifact;
* ``artifact_only`` - the model gets metadata and a retrieval handle because even
  an excerpt would be noise.

Nothing is deleted, nothing is rewritten, and :func:`retrieve` re-hashes the file
before returning it: an artifact whose digest does not match is refused as
evidence rather than silently trusted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from . import contracts
from .contracts import ContractError
from .serialization import digest_bytes

ARTIFACT_DIR = "evidence/artifacts"
ARTIFACT_SCHEMA = 1

DEFAULT_EXTERNALIZE_AT_BYTES = 8192
"""Measured default: packets in the benchmark run 21-51 KB and the AR-203
verification artifacts run 0.3-12 KB, so 8 KB is the point below which inline
output is genuinely cheap and above which a reference is worth its indirection.
The value is configurable; it is a threshold, not a law."""

DEFAULT_EXCERPT_BYTES = 2048
DEFAULT_TAIL_BYTES = 1024

STATUS_INLINE = "fully_inline"
STATUS_EXCERPT = "inline_excerpt_plus_artifact"
STATUS_ARTIFACT_ONLY = "artifact_only"

OVERFLOW_STATUSES = (STATUS_INLINE, STATUS_EXCERPT, STATUS_ARTIFACT_ONLY)


def overflow_status(size: int, *, threshold: int = DEFAULT_EXTERNALIZE_AT_BYTES,
                    excerpt_bytes: int = DEFAULT_EXCERPT_BYTES) -> str:
    if int(size) <= int(threshold):
        return STATUS_INLINE
    if int(size) <= int(threshold) * 4 + int(excerpt_bytes):
        return STATUS_EXCERPT
    return STATUS_ARTIFACT_ONLY


def summarise_output(data: bytes | str) -> dict:
    """A deterministic, evidence-safe summary: counts only, never a rewrite."""
    text = data.decode("utf-8", errors="replace") if isinstance(data, (bytes, bytearray)) else str(data)
    lines = text.splitlines()
    lowered = [line.lower() for line in lines]
    errors = [line for line in lines if "error" in line.lower() or "traceback" in line.lower()]
    warnings = [line for line in lines if "warning" in line.lower() or "warn" in line.lower()]
    failed = [line for line in lines if "fail" in line.lower()]
    return {
        "lines": len(lines),
        "bytes": len(text.encode("utf-8")),
        "error_lines": len(errors),
        "warning_lines": len(warnings),
        "failure_lines": len(failed),
        "first_line": lines[0][:200] if lines else "",
        "last_line": lines[-1][:200] if lines else "",
        "empty": not lines or all(not line.strip() for line in lines),
        "lowered_head": lowered[:1],
    }


def excerpt_of(text: str, *, excerpt_bytes: int = DEFAULT_EXCERPT_BYTES,
               tail_bytes: int = DEFAULT_TAIL_BYTES) -> dict:
    """A bounded head/tail excerpt with the byte accounting that produced it."""
    encoded = text.encode("utf-8")
    if len(encoded) <= excerpt_bytes + tail_bytes:
        return {"head": text, "tail": "", "excerpted": False, "omitted_bytes": 0}
    head = encoded[:excerpt_bytes].decode("utf-8", errors="ignore")
    tail = encoded[-tail_bytes:].decode("utf-8", errors="ignore") if tail_bytes else ""
    return {
        "head": head,
        "tail": tail,
        "excerpted": True,
        "omitted_bytes": len(encoded) - len(head.encode("utf-8")) - len(tail.encode("utf-8")),
    }


def artifact_path(root: Path, digest: str) -> Path:
    return Path(root) / ARTIFACT_DIR / f"{digest}.log"


def externalize(
    root: Path,
    *,
    data: bytes | str,
    tool: str,
    source_execution: str = "",
    command: str = "",
    task_id: str = "",
    run_id: str = "",
    threshold: int = DEFAULT_EXTERNALIZE_AT_BYTES,
    excerpt_bytes: int = DEFAULT_EXCERPT_BYTES,
    tail_bytes: int = DEFAULT_TAIL_BYTES,
    force: bool = False,
) -> dict:
    """Store one tool output as an artifact and return its reference record.

    Small outputs are returned inline with the record's status naming that fact;
    nothing is externalized merely because a threshold exists.
    """
    raw = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    digest = digest_bytes(raw)
    size = len(raw)
    status = overflow_status(size, threshold=threshold, excerpt_bytes=excerpt_bytes)
    if force and status == STATUS_INLINE:
        status = STATUS_EXCERPT
    text = raw.decode("utf-8", errors="replace")
    summary = summarise_output(raw)
    excerpt = excerpt_of(text, excerpt_bytes=excerpt_bytes, tail_bytes=tail_bytes)
    record = {
        "schema_version": ARTIFACT_SCHEMA,
        "artifact_id": contracts.new_record_id("art"),
        "tool": str(tool),
        "command": str(command),
        "source_execution": str(source_execution),
        "task_id": str(task_id),
        "run_id": str(run_id),
        "sha256": digest,
        "size": size,
        "created_at": contracts.utc_now(),
        "summary": summary,
        "excerpt": {"head": excerpt["head"], "tail": excerpt["tail"], "excerpted": excerpt["excerpted"],
                    "omitted_bytes": excerpt["omitted_bytes"]},
        "status": status,
        "stored": False,
        "path": "",
        "inline_text": text if status == STATUS_INLINE else "",
        "note": (
            "the artifact is the evidence; the summary and excerpt are a model-facing convenience and "
            "are never a replacement for it"
        ),
    }
    if status != STATUS_INLINE:
        target_dir = Path(root) / ARTIFACT_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_path(Path(root), digest)
        if not path.is_file():
            path.write_bytes(raw)
        record["stored"] = True
        record["path"] = str(path)
        record["relative_path"] = f"{ARTIFACT_DIR}/{digest}.log"
    return record


def verify_artifact(record: Mapping) -> dict:
    """Re-hash the stored artifact. A mismatch is a refusal, not a warning."""
    path = str(record.get("path", ""))
    expected = str(record.get("sha256", ""))
    if not path:
        return {"ok": False, "problems": ["the artifact record has no stored path"], "size": 0}
    file = Path(path)
    if not file.is_file():
        return {"ok": False, "problems": [f"the artifact is missing: {path}"], "size": 0}
    raw = file.read_bytes()
    actual = digest_bytes(raw)
    if actual != expected:
        return {
            "ok": False,
            "problems": [f"the artifact digest changed: recorded {expected}, found {actual}"],
            "size": len(raw),
        }
    return {"ok": True, "problems": [], "size": len(raw), "sha256": actual}


def retrieve(record: Mapping) -> dict:
    """Return the full artifact, refusing a record whose digest does not match."""
    verdict = verify_artifact(record)
    if not verdict["ok"]:
        return {
            "ok": False,
            "problems": verdict["problems"],
            "text": "",
            "note": "a reference whose artifact is unreadable or changed is not evidence",
        }
    raw = Path(str(record["path"])).read_bytes()
    return {
        "ok": True,
        "problems": [],
        "text": raw.decode("utf-8", errors="replace"),
        "bytes": len(raw),
        "sha256": verdict["sha256"],
    }


def render_for_model(record: Mapping, *, tool_label: str = "") -> str:
    """The bounded model-facing block that replaces the raw output in history."""
    status = str(record.get("status", STATUS_INLINE))
    if status == STATUS_INLINE:
        return str(record.get("inline_text", ""))
    summary = record.get("summary") if isinstance(record.get("summary"), Mapping) else {}
    excerpt = record.get("excerpt") if isinstance(record.get("excerpt"), Mapping) else {}
    label = str(tool_label or record.get("tool", "tool"))
    lines = [
        f"{label} output externalized ({status}).",
        f"Exit/summary: {summary.get('lines', 0)} lines, {record.get('size', 0)} bytes, "
        f"{summary.get('error_lines', 0)} error line(s).",
        f"Artifact: {record.get('relative_path') or record.get('path', '')}",
        f"SHA256: {record.get('sha256', '')}",
        f"Size: {record.get('size', 0)} bytes",
    ]
    if excerpt.get("head"):
        lines.extend(["", "Relevant head:", str(excerpt["head"])])
    if excerpt.get("tail"):
        lines.extend(["", "Relevant tail:", str(excerpt["tail"])])
    if excerpt.get("excerpted"):
        lines.append(f"[{excerpt.get('omitted_bytes', 0)} bytes omitted from the model-facing view; "
                     "the artifact carries every byte]")
    return "\n".join(lines)


def retrieve_reference(record: Mapping) -> str:
    """The short retrieval instruction a model can act on."""
    return (
        f"Read the full output from {record.get('relative_path') or record.get('path', '')} "
        f"(sha256 {record.get('sha256', '')}) if you need more than the excerpt."
    )


__all__ = [
    "ARTIFACT_DIR",
    "ARTIFACT_SCHEMA",
    "DEFAULT_EXTERNALIZE_AT_BYTES",
    "DEFAULT_EXCERPT_BYTES",
    "DEFAULT_TAIL_BYTES",
    "STATUS_INLINE",
    "STATUS_EXCERPT",
    "STATUS_ARTIFACT_ONLY",
    "OVERFLOW_STATUSES",
    "overflow_status",
    "summarise_output",
    "excerpt_of",
    "artifact_path",
    "externalize",
    "verify_artifact",
    "retrieve",
    "render_for_model",
    "retrieve_reference",
]
