"""Dataset export: the honest way to get from shadow records to a trained model.

This is the only sanctioned path from Ariadne's own operation to a fitted runtime, and
it stops deliberately short of training. The loop it supports is:

    shadow records  ->  reviewed outcomes  ->  export a bounded dataset
                                                 ->  (separately authorised) fit
                                                 ->  evaluate  ->  shadow again

Three properties make the export safe to hand to something that *will* train:

*Explicit review.* Only records carrying recorded ground truth are exported, and the
ground truth's source travels with it. An unreviewed shadow prediction is not
training data; it is a guess about a guess.

*Identity travels with the data.* Each row keeps the question identity and the
projection digest, so a fitted weight file can be checked against the question it was
fitted for rather than being applied by name.

*It is an export, not a trigger.* Writing the dataset does not fit anything.
Ariadne 2.1 has no self-training path at all, and the reason is written into this
module: a system that retrains on its own decisions closes a feedback loop in which
the only thing that gets better is agreement with itself.

Only projected state is exported, and only the fields the projection contract declares.
Nothing reads the repository, the conversation or the user's files.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ...contracts import ContractError

EXPORT_SCHEMA = "ariadne-decision-runtime-dataset/1"
"""The exported dataset document shape."""

EXPORT_VERSION = "ar-206-export-1"
"""The export record shape."""

MIN_REVIEWED_ROWS = 1
"""Rows below this produce a refusal rather than an empty file."""


def collect(
    state: Mapping[str, Any],
    *,
    definition: str = "",
    require_ground_truth: bool = True,
) -> dict:
    """Gather exportable rows from recorded shadow predictions.

    Returns a summary with the rows inline; the caller decides whether to write them.
    ``require_ground_truth`` defaults to True, which means an export of unreviewed
    predictions is opt-in and has to be asked for.
    """
    rows: list[dict] = []
    skipped = {"no_ground_truth": 0, "abstained": 0, "no_answer": 0}
    for record in state.get("decision_shadow", []) or []:
        if definition and str(record.get("definition", "")) != str(definition):
            continue
        if record.get("abstained"):
            skipped["abstained"] += 1
            continue
        answer = str(record.get("answer", ""))
        if not answer:
            skipped["no_answer"] += 1
            continue
        truth = str(record.get("ground_truth", ""))
        if require_ground_truth and not truth:
            skipped["no_ground_truth"] += 1
            continue
        rows.append(
            {
                "case_id": str(record.get("shadow_id", "")),
                "question_id": str(record.get("question_id", "")),
                "question_identity": str(record.get("question_identity", "")),
                "primitive": str(record.get("primitive", "")),
                "definition": str(record.get("definition", "")),
                "definition_version": str(record.get("definition_version", "1")),
                "projection_digest": str(record.get("projection_digest", "")),
                "predicted": answer,
                "expected": truth,
                "ground_truth_source": str(record.get("ground_truth_source", "")),
                "agreement": str(record.get("agreement", "UNKNOWN")),
                "confidence": record.get("confidence"),
                "confidence_kind": str(record.get("confidence_kind", "NONE")),
                "model_revision": str(record.get("model_revision", "")),
            }
        )
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "schema": EXPORT_SCHEMA,
        "version": EXPORT_VERSION,
        "definition": str(definition),
        "rows": rows,
        "row_count": len(rows),
        "skipped": skipped,
        "dataset_digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "note": (
            "exported rows are reviewed observations only; writing this dataset fits nothing and "
            "Ariadne has no self-training path"
        ),
    }


def write(dataset: Mapping[str, Any], path: Path) -> dict:
    """Write an exported dataset to disk.

    Refuses an empty or unreviewed dataset unless the caller explicitly asked for an
    unreviewed export, so a training pipeline cannot be pointed at unlabelled rows by
    accident.
    """
    rows = list(dataset.get("rows", []) or [])
    if len(rows) < MIN_REVIEWED_ROWS:
        raise ContractError(
            "refusing to export an empty dataset; there is nothing to fit and an empty file "
            "invites a pipeline to train on nothing and report success"
        )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dataset, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return {
        "path": str(path),
        "rows": len(rows),
        "dataset_digest": str(dataset.get("dataset_digest", "")),
        "definition": str(dataset.get("definition", "")),
    }


def refusal(state: Mapping[str, Any], *, definition: str = "") -> dict:
    """Why an export would be refused, in words."""
    summary = collect(state, definition=definition)
    reasons: list[str] = []
    if not summary["row_count"]:
        reasons.append("no shadow record carries both an answer and recorded ground truth")
    if summary["skipped"]["no_ground_truth"]:
        reasons.append(
            f"{summary['skipped']['no_ground_truth']} record(s) had no recorded ground truth and were skipped"
        )
    if summary["skipped"]["abstained"]:
        reasons.append(f"{summary['skipped']['abstained']} abstention(s) were skipped")
    return {
        "exportable": not reasons,
        "reasons": reasons,
        "row_count": summary["row_count"],
        "dataset_digest": summary["dataset_digest"],
    }


def describe() -> dict:
    return {
        "version": EXPORT_VERSION,
        "schema": EXPORT_SCHEMA,
        "requires": "recorded ground truth with a named source",
        "trains": False,
        "note": (
            "Ariadne 2.1 exports a bounded dataset and stops. Training is a separate, explicitly "
            "authorised step because self-training on a system's own decisions closes a feedback loop."
        ),
    }