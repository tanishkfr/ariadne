#!/usr/bin/env python3
"""2.4B mutation suite: do the intelligence/efficiency guards actually bite?

Each mutation removes or inverts one load-bearing check and the named 2.4B test
must go red. A survivor is a boundary that is not enforced, not a reason to
weaken the test. The runner, transactional ledger and restoration proof are the
AR-24A harness's, reused deliberately: one mutation protocol, not two.
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
AR24B = ROOT / "scripts" / "test-ar24b.py"

test = SUPPORT.test

MUTATIONS: list[dict] = [
    {
        "id": "M01",
        "boundary": "completed is not accepted",
        "rule": "a pending human decision is counted as accepted",
        "edits": [{
            "path": ENGINE / "measurement.py",
            "before": '            acceptance_value == "accepted",',
            "after": '            acceptance_value in ("accepted", "PENDING_HUMAN_DECISION"),  # mutation',
        }],
        "tests": [test(AR24B, "measurement_separates_completed_from_accepted")],
        "why": "the whole report exists to keep a completed attempt separate from a human acceptance.",
    },
    {
        "id": "M02",
        "boundary": "unknown is not zero",
        "rule": "an unmeasured numeric field is reported as zero",
        "edits": [{
            "path": ENGINE / "measurement.py",
            "before": (
                '        "input_tokens": _field(\n'
                '            _number_or_unknown(measured_values.get("input_tokens")),\n'
                '            provenance=REPORTED if measured_values.get("input_tokens") is not None else UNKNOWN,'
            ),
            "after": (
                '        "input_tokens": _field(\n'
                '            _number_or_unknown(measured_values.get("input_tokens")) or 0,\n'
                '            provenance=REPORTED,'
            ),
        }],
        "tests": [test(AR24B, "measurement_unknown_is_not_zero_and_supersede_preserves_history")],
        "why": "a missing measurement rendered as zero is the cheapest way to make a report look better.",
    },
    {
        "id": "M03",
        "boundary": "small samples cannot qualify",
        "rule": "an alternative with fewer than the minimum samples is treated as qualified",
        "edits": [{
            "path": ENGINE / "model_evidence.py",
            "before": '        elif len(group) >= MIN_QUALIFIED_SAMPLES and len(validated) >= MIN_QUALIFIED_VALIDATED:',
            "after": '        elif len(validated) >= MIN_QUALIFIED_VALIDATED:  # mutation: sample size is decorative',
        }],
        "tests": [test(AR24B, "insufficient_sample_size_cannot_produce_a_qualification")],
        "why": "a few attempts are an observation, not a model ranking.",
    },
    {
        "id": "M04",
        "boundary": "stale evidence cannot control",
        "rule": "stale model observations are treated as current",
        "edits": [{
            "path": ENGINE / "model_evidence.py",
            "before": '        elif not current or not revision_current:',
            "after": '        elif False:  # mutation: age and revision drift do not matter',
        }],
        "tests": [test(AR24B, "stale_performance_data_is_not_used")],
        "why": "a model revision or provider can change; old evidence cannot speak for it.",
    },
    {
        "id": "M05",
        "boundary": "uncertain identity is not qualification",
        "rule": "an observation with no observed provider/model is still qualified",
        "edits": [{
            "path": ENGINE / "model_evidence.py",
            "before": '        if not identity_known:',
            "after": '        if False:  # mutation: an unknown identity can qualify',
        }],
        "tests": [test(AR24B, "invalid_model_identity_is_not_qualified")],
        "why": "a capability cannot be attached to a model nobody observed.",
    },
    {
        "id": "M06",
        "boundary": "review independence",
        "rule": "the implementer is eligible for the independent-review role",
        "edits": [{
            "path": ENGINE / "model_evidence.py",
            "before": (
                '    independent = {str(item) for item in independent_of if str(item).strip()}\n'
                '    if role == "independent-review":'
            ),
            "after": (
                '    independent = {str(item) for item in independent_of if str(item).strip()}\n'
                '    if False:  # mutation: independence is not filtered'
            ),
        }],
        "tests": [test(AR24B, "review_independence_excludes_the_implementer")],
        "why": "model evidence must never override the independence boundary.",
    },
    {
        "id": "M07",
        "boundary": "promotion gate",
        "rule": "a qualified record reorders adapters without a recorded human promotion",
        "edits": [{
            "path": ENGINE / "model_evidence.py",
            "before": '            not require_promotion\n            or promoted_scope(',
            "after": '            True\n            or promoted_scope(',
        }],
        "tests": [test(AR24B, "unqualified_or_unpromoted_evidence_cannot_reorder_adapters")],
        "why": "shadow evidence must not change execution merely because it exists.",
    },
    {
        "id": "M08",
        "boundary": "context cache invalidation",
        "rule": "a changed source keeps its cached hash",
        "edits": [{
            "path": ENGINE / "context.py",
            "before": '    if int(entry.get("mtime_ns", -1)) != int(current.get("mtime_ns", -2)):',
            "after": '    if False and int(entry.get("mtime_ns", -1)) != int(current.get("mtime_ns", -2)):',
        }],
        "tests": [test(AR24B, "context_cache_invalidates_after_source_modification")],
        "why": "a cache hit on changed bytes is stale context pretending to be current.",
    },
    {
        "id": "M09",
        "boundary": "adaptive reduction keeps required context",
        "rule": "adaptive reduction never applies, so the measured benefit disappears",
        "edits": [{
            "path": ENGINE / "context.py",
            "before": '            str(reduction) == "adaptive"\n            and str(candidate.get("kind", "")) == "project-scope-file"',
            "after": '            str(reduction) == "off"\n            and str(candidate.get("kind", "")) == "project-scope-file"',
        }],
        "tests": [test(AR24B, "adaptive_reduction_omits_only_unchanged_optional_scope_and_measures_bytes")],
        "why": "the optimisation needs a test that notices when it silently stops reducing anything.",
    },
    {
        "id": "M10",
        "boundary": "continuation freshness",
        "rule": "a continuation for another revision is resumed anyway",
        "edits": [
            {
                "path": ENGINE / "continuation.py",
                "before": '    if str(record.get("status", "")) != "CURRENT":',
                "after": '    if False:  # mutation: status is not checked',
            },
            {
                "path": ENGINE / "continuation.py",
                "before": '    if str(revision_hash) and recorded != str(revision_hash):',
                "after": '    if False and str(revision_hash) and recorded != str(revision_hash):',
            },
        ],
        "tests": [test(AR24B, "continuation_refuses_a_stale_revision_and_resumes_a_current_one")],
        "why": "a resumed worker reading a stale projection works from evidence that no longer applies.",
    },
    {
        "id": "M11",
        "boundary": "skill registry integrity",
        "rule": "a skill proposal applies itself to the trusted registry",
        "edits": [{
            "path": ENGINE / "skill_intelligence.py",
            "before": '    raise ContractError(\n        "a skill proposal cannot modify the trusted registry automatically; "',
            "after": '    return {"applied": True}  # mutation\n    raise ContractError(\n        "a skill proposal cannot modify the trusted registry automatically; "',
        }],
        "tests": [test(AR24B, "skill_proposals_are_reviewed_and_never_applied_automatically")],
        "why": "an external or model-authored lesson must not become trusted policy by itself.",
    },
    {
        "id": "M12",
        "boundary": "stale context packet",
        "rule": "a context decision with no current revision is replayed",
        "edits": [{
            "path": ENGINE / "context.py",
            "before": '    problems: list[str] = []\n    recorded_revision = str(decision.get("revision_hash", "") or "")',
            "after": '    return []  # mutation: any context decision is current\n    problems: list[str] = []\n'
                     '    recorded_revision = str(decision.get("revision_hash", "") or "")',
        }],
        "tests": [test(AR24B, "context_cache_is_isolated_between_projects_and_a_stale_packet_is_refused")],
        "why": "a packet decision from another revision must be refused, never guessed into the present.",
    },
]


if __name__ == "__main__":
    SUPPORT.MUTATIONS = MUTATIONS
    SUPPORT.HARNESS = "ar24b-mutations"
    sys.exit(SUPPORT.main(sys.argv[1:]))
