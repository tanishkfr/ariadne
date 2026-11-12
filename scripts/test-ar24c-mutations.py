#!/usr/bin/env python3
"""2.4C mutation suite: do the design/proof/host boundaries actually bite?

Each mutation removes one 2.4C guard and the named test must go red. The
transactional ledger, baseline check and restoration proof are the 2.4A
harness's, reused deliberately: one mutation protocol, not two.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location("ar24a_mutations", ROOT / "scripts" / "test-ar24a-mutations.py")
SUPPORT = importlib.util.module_from_spec(_spec)
sys.modules["ar24a_mutations"] = SUPPORT
_spec.loader.exec_module(SUPPORT)

ENGINE = ROOT / "src" / "ariadne_engine"
AR24C = ROOT / "scripts" / "test-ar24c.py"
AR24B = ROOT / "scripts" / "test-ar24b.py"
RENDERED = ROOT / "scripts" / "test-rendered-critique.py"

test = SUPPORT.test

MUTATIONS: list[dict] = [
    {
        "id": "M01",
        "boundary": "stale creative review",
        "rule": "a review bound to a replaced S5 packet is still current",
        "edits": [{
            "path": ENGINE / "creative_proof.py",
            "before": '    if str(binding.get("packet_digest", "")) != str(manifest.get("packet_sha256", "")):',
            "after": '    if False:  # mutation: the packet digest is decorative',
        }],
        "tests": [test(AR24C, "a_stale_s5_packet_digest_is_refused")],
        "why": "a replaced review packet must make the old review stale.",
    },
    {
        "id": "M02",
        "boundary": "review substitution",
        "rule": "the latest review is used even when it belongs to another packet",
        "edits": [{
            "path": ENGINE / "creative_proof.py",
            "before": (
                '    packet_path = Path(packet) if packet is not None else Path(str(packet_row.get("path", "")))\n'
                '    manifest = _manifest(packet_path)\n'
                '    packet_id = str(manifest.get("packet_id") or packet_path.name)\n'
                '    record = review.current_review(state, packet_id=packet_id)'
            ),
            "after": (
                '    packet_path = Path(packet) if packet is not None else Path(str(packet_row.get("path", "")))\n'
                '    manifest = _manifest(packet_path)\n'
                '    packet_id = str(manifest.get("packet_id") or packet_path.name)\n'
                '    record = (review.reviews(state) or [None])[-1]  # mutation: any review will do'
            ),
        }],
        "tests": [test(AR24C, "another_attempts_review_cannot_satisfy_the_current_packet")],
        "why": "a correction attempt must not inherit the previous attempt's review.",
    },
    {
        "id": "M03",
        "boundary": "review evidence digest",
        "rule": "a changed review judgement is still the reviewed evidence",
        "edits": [{
            "path": ENGINE / "creative_proof.py",
            "before": '    elif str(record.get("review_judgement_sha256")) != _sha256_file(judgement):',
            "after": '    elif False:  # mutation: the judgement digest is not checked',
        }],
        "tests": [test(AR24C, "a_changed_judgement_file_invalidates_the_review_digest")],
        "why": "the digest is what binds the review to the judgement the reviewer actually wrote.",
    },
    {
        "id": "M04",
        "boundary": "human G3 authority",
        "rule": "G3 is satisfied without any recorded human approval",
        "edits": [{
            "path": ENGINE / "policy.py",
            "before": "    if not records:\n        return False, (",
            "after": '    if not records:\n        return True, "mutation: no G3 approval is needed"',
        }],
        "tests": [test(AR24C, "g3_is_still_a_human_owned_decision_after_a_passing_review")],
        "why": "a passing review and a proof receipt are not a human decision.",
    },
    {
        "id": "M05",
        "boundary": "accessibility finding",
        "rule": "measured contrast failures are silently dropped",
        "edits": [{
            "path": ENGINE / "rendered_critique" / "evidence.py",
            "before": "    if contrast_failures:",
            "after": "    if False:  # mutation: contrast failures are dropped",
        }],
        "tests": [test(AR24C, "accessibility_checks_catch_contrast_focus_dialog_and_form_defects")],
        "why": "a passing automated audit must not hide a measured contrast defect.",
    },
    {
        "id": "M06",
        "boundary": "stale rendered evidence",
        "rule": "a capture bound to an older source digest remains current",
        "edits": [{
            "path": ENGINE / "rendered_critique" / "source.py",
            "before": "    if recorded != current_digest:",
            "after": "    if False:  # mutation: a moved source is still current",
        }],
        "tests": [test(RENDERED, "editing_a_relevant_stylesheet_makes_an_old_capture_stale")],
        "why": "an old screenshot cannot describe a changed stylesheet.",
    },
    {
        "id": "M07",
        "boundary": "wrong viewport",
        "rule": "evidence for one viewport answers a request for another",
        "edits": [{
            "path": ENGINE / "render.py",
            "before": (
                "    if viewport_width:\n"
                "        rows = [\n"
                "            record for record in rows\n"
                "            if str((record.get(\"viewport\") or {}).get(\"width\", \"\")) == str(viewport_width)\n"
                "        ]"
            ),
            "after": "    if False:  # mutation: every viewport answers every query",
        }],
        "tests": [test(AR24C, "wrong_viewport_evidence_does_not_satisfy_the_requested_width")],
        "why": "a 390px capture is not evidence about a 1440px layout.",
    },
    {
        "id": "M08",
        "boundary": "host proof integrity",
        "rule": "a forged proof receipt is projected as valid host state",
        "edits": [{
            "path": ENGINE / "host.py",
            "before": "        integrity.extend(proof_module.receipt_problems(proof))",
            "after": "        integrity.extend([])  # mutation: receipt integrity is not checked",
        }],
        "tests": [test(AR24C, "a_forged_host_proof_state_is_reported_invalid")],
        "why": "a host must not display a forged acceptance state as the engine's proof.",
    },
    {
        "id": "M09",
        "boundary": "event cursor",
        "rule": "an unknown cursor is accepted and the log is replayed from nowhere",
        "edits": [{
            "path": ENGINE / "host.py",
            "before": (
                "        if found is None or str(found.get(\"digest\", \"\")) != digest or (\n"
                "            event_id and str(found.get(\"event_id\", \"\")) != event_id\n"
                "        ):"
            ),
            "after": "        if False:  # mutation: an unknown cursor is treated as current",
        }],
        "tests": [test(AR24C, "an_unknown_host_cursor_is_refused_not_replayed")],
        "why": "a host that resumes from a stale cursor would duplicate transitions.",
    },
    {
        "id": "M10",
        "boundary": "cross-task review leakage",
        "rule": "a review for any packet satisfies the current review lookup",
        "edits": [{
            "path": ENGINE / "review.py",
            "before": (
                "        if packet_id and str(record.get(\"packet_id\", \"\")) != packet_id:\n"
                "            continue"
            ),
            "after": "        if False:  # mutation: any packet's review is close enough",
        }],
        "tests": [test(AR24C, "another_attempts_review_cannot_satisfy_the_current_packet")],
        "why": "review identity is bound to the packet, not to the run's latest prose.",
    },
    {
        "id": "M11",
        "boundary": "context mandatory sources",
        "rule": "adaptive context reduction may omit a required source",
        "edits": [
            {
                "path": ENGINE / "context.py",
                "before": '        if candidate.get("required"):',
                "after": "        if False:  # mutation: required sources are not forced",
            },
            {
                "path": ENGINE / "context.py",
                "before": (
                    '            and str(candidate.get("kind", "")) == "project-scope-file"\n'
                    '            and not bool(candidate.get("required"))'
                ),
                "after": (
                    "            and True  # mutation: the optional/required distinction is dropped\n"
                    "            and True  # mutation: any kind may be omitted"
                ),
            },
        ],
        "tests": [test(AR24B, "adaptive_reduction_omits_only_unchanged_optional_scope_and_measures_bytes")],
        "why": "adaptive reduction saves bytes only by omitting optional duplication, not instructions.",
    },
    {
        "id": "M12",
        "boundary": "model routing promotion",
        "rule": "a qualified adapter is applied without a recorded human promotion",
        "edits": [{
            "path": ENGINE / "model_evidence.py",
            "before": (
                "        and (\n"
                "            not require_promotion\n"
                "            or promoted_scope("
            ),
            "after": (
                "        and (\n"
                "            True\n"
                "            or promoted_scope("
            ),
        }],
        "tests": [test(AR24B, "unqualified_or_unpromoted_evidence_cannot_reorder_adapters")],
        "why": "shadow evidence must never become a route change without a human promotion.",
    },
]


def main(argv: list[str] | None = None) -> int:
    SUPPORT.MUTATIONS = MUTATIONS
    SUPPORT.HARNESS = "ar24c-mutations"
    return SUPPORT.main(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
