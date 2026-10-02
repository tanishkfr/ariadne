#!/usr/bin/env python3
"""Packet-level proof for Ariadne's minimal writing execution path."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("ariadne_transport", ROOT / "scripts" / "prepare-stage.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Could not load writing transport")
TRANSPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRANSPORT)


def args(root: Path, phase: str, output: Path, request: Path, draft: Path | None = None, review: Path | None = None, original: Path | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        phase=phase,
        intent="HUMAN-DRAFT TRANSFORMATION",
        request_file=str(request),
        output=str(output),
        packet_id=output.name,
        provider="codex",
        model="fixture-model",
        criteria="Preserve ideas and voice; improve clarity; state uncertainty.",
        source_file=[],
        draft_file=str(draft) if draft else None,
        original_draft_file=str(original) if original else None,
        review_file=str(review) if review else None,
    )


def main() -> int:
    checks: list[tuple[str, bool]] = []
    with tempfile.TemporaryDirectory(prefix="ariadne-writing-execution-") as value:
        root = Path(value)
        request = root / "request.txt"
        original = root / "original-draft.txt"
        draft = root / "final-draft.txt"
        review = root / "review.txt"
        request.write_text("Improve this user's draft without replacing their voice.\n", encoding="utf-8")
        original.write_text("I kept opening the folder because the name was still there.\n", encoding="utf-8")
        draft.write_text("I kept opening the folder because seeing the name still there mattered.\n", encoding="utf-8")
        review.write_text("PASS\nThe idea and voice remain recognizable.\n", encoding="utf-8")

        draft_args = args(root, "draft", root / "draft-packet", request, original)
        cli_result = subprocess.run(
            [
                "python", str(ROOT / "scripts" / "prepare-stage.py"), "prepare-writing",
                "--phase", "draft", "--intent", draft_args.intent,
                "--request-file", str(request), "--output", str(root / "draft-packet"),
                "--packet-id", "draft-packet", "--provider", "codex", "--model", "fixture-model",
                "--criteria", draft_args.criteria, "--draft-file", str(original),
            ],
            cwd=ROOT, capture_output=True, text=True,
        )
        draft_packet = root / "draft-packet"
        draft_manifest = json.loads((draft_packet / "manifest.json").read_text(encoding="utf-8"))
        checks.append(("writing CLI command prepares a packet", cli_result.returncode == 0))
        checks.append(("writing intent is recognized", draft_manifest["intent"] == "HUMAN-DRAFT TRANSFORMATION"))
        checks.append(("relevant guidance is selected", any("writing-transformation.md" in item["path"] for item in draft_manifest["sources"])))
        checks.append(("provider/model packet is produced", draft_manifest["provider"] == "codex" and draft_manifest["model"] == "fixture-model"))
        checks.append(("draft artifact is classified", draft_manifest["packet_kind"] == "writing" and "writing-draft" in (draft_packet / "packet.txt").read_text(encoding="utf-8")))
        checks.append(("draft packet maps to S4", draft_manifest["workflow_stages"] == ["S4"] and draft_manifest["live_execution"] is False))
        checks.append(("draft packet verifies", not TRANSPORT.verify_writing_packet(draft_packet)))

        review_packet = TRANSPORT.prepare_writing(args(root, "review", root / "review-packet", request, draft=draft, original=original))
        review_manifest = json.loads((review_packet / "manifest.json").read_text(encoding="utf-8"))
        review_text = (review_packet / "packet.txt").read_text(encoding="utf-8")
        checks.append(("review packet is independent", review_manifest["independent_review"] is True and review_manifest["workflow_stages"] == ["S5"]))
        checks.append(("review packet includes request and both drafts", all(label in review_text for label in ("original user request", "original draft", "final writing draft"))))
        checks.append(("review packet excludes rationale context", all(term not in review_manifest["sources"] for term in ("drafting rationale", "hidden reasoning", "implementation history"))))
        checks.append(("review packet verifies", not TRANSPORT.verify_writing_packet(review_packet)))

        revise_packet = TRANSPORT.prepare_writing(args(root, "revise", root / "revise-packet", request, draft=draft, review=review, original=original))
        revise_manifest = json.loads((revise_packet / "manifest.json").read_text(encoding="utf-8"))
        checks.append(("revision packet carries draft and review", {item["label"] for item in revise_manifest["sources"]} >= {"final writing draft", "independent editorial review"}))
        checks.append(("revision stays in existing S4 boundary", revise_manifest["workflow_stages"] == ["S4"]))

        try:
            TRANSPORT.prepare_writing(args(root, "draft", root / "social-packet", request))
            social_blocked = False
        except TRANSPORT.PacketError:
            social_blocked = True
        checks.append(("SOCIAL remains isolated", social_blocked))

    print("ARIADNE WRITING PACKET EXECUTION SELF-TEST\n")
    failed = []
    for name, passed in checks:
        print(("ok    " if passed else "FAIL  ") + name)
        if not passed:
            failed.append(name)
    print(f"\n{'FAILED' if failed else 'PASS'}  {len(checks) - len(failed)}/{len(checks)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
