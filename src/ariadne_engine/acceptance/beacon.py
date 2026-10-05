"""Two proof-pass slices over real records, and one that is deliberately a fixture.

**The Beacon slice is history.** Beacon is the AR-221 fixture, rendered by real Chromium
during AR-222, and its outcome is preserved verbatim in
``docs/v2/2.2/20-AR-222-RESULTS.md``: six captures per pass, mechanical validation passing
twice, two persistent findings, and one of them still major after a bounded repair. Nothing
here edits that document or improves its ending. The requirement that the log table must not
clip below 768px is ``FAILED`` because at 390px the table reached 568px, and the pass that
follows a fixture-supplied worker claim of completion finds that claim ``CONTRADICTED`` by the
same measurement. AR-222 wrote "Visual acceptance NOT_CLAIMED; human acceptance NOT_GRANTED"
into its own results; this module produces the same conclusion from records rather than from
a sentence somebody wrote.

**The repair slice is a fixture, and says so.** AR-222's repair improved its defect without
eliminating it, which is the honest outcome and not a demonstration of a failed-to-proven
transition. So the ``FAILED -> repair -> PROVEN`` demonstration runs on a separate controlled
fixture where the conclusion is not a rewrite of a real project's history.

**The keyboard requirement is UNPROVEN, not FAILED.** History has a build result and
screenshots for keyboard behaviour and nothing else. No observation of a violation exists, and
turning absent evidence into failure is the single easiest way for an acceptance engine to
become dishonest.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from . import claims, contract, decisions, evidence, gates, invalidation, requirements

BEACON_VERSION = "ar-223-beacon-slice-1"

RESULTS_DOCUMENT = Path("docs") / "v2" / "2.2" / "20-AR-222-RESULTS.md"
"""The preserved AR-222 result. Read-only, and required to exist."""

BEACON_WORK_DIGEST_PREFIX = "ar222-preserved-run"
"""Why the work digest below is the digest of the results document.

The captures this slice reads no longer exist as files; what survives is the results document
that records them. So the work revision is identified by that document's own digest rather than
by an invented constant, which means an edit to the history changes the digest and every
evidence row stops being current instead of quietly continuing to support a verdict.
"""


def beacon_work_digest(root: Path | str) -> str:
    """The work digest of the preserved run: the digest of the document that records it."""
    import hashlib

    path = Path(root) / RESULTS_DOCUMENT
    text = path.read_text(encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


REQUIRED_MARKERS = (
    "RENDERED_WITH_KNOWN_FINDINGS",
    "390px",
    "568px",
    "persistent",
    "Hidden overflow",
    "NOT_CLAIMED",
    "NOT_GRANTED",
)
"""The phrases that must still be present for this slice to mean anything.

If a future edit to the results document removes any of them, the history this module reads
has changed shape and the slice should stop being trusted rather than quietly adapt. A check
on history is the only thing that makes a fixture of history honest.
"""

BEACON_REQUEST = (
    "Render the Beacon desktop tool, critique the rendered result independently, apply bounded "
    "repairs where the critique supports them, and report what is actually established."
)
"""The request as AR-222 received it. Used verbatim so the contract binds to it."""


def assert_history(root: Path | str) -> dict:
    """Confirm the preserved results document still says what this slice depends on."""
    path = Path(root) / RESULTS_DOCUMENT
    if not path.is_file():
        raise FileNotFoundError(
            f"the preserved AR-222 results are not at {path}; the Beacon slice reads real history "
            "and refuses to substitute a fixture for it"
        )
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in REQUIRED_MARKERS if marker not in text]
    if missing:
        raise FileNotFoundError(
            f"the preserved AR-222 results no longer contain: {', '.join(missing)}. This slice reads "
            "that history; if it has changed, the slice's verdicts need re-deriving, not re-running"
        )
    return {
        "path": str(path),
        "bytes": len(text.encode("utf-8")),
        "markers": list(REQUIRED_MARKERS),
        "immutable": True,
    }


def beacon_state(root: Path | str, *, work_digest: str = "") -> dict:
    """Build the acceptance state for the Beacon slice from its preserved evidence.

    Every evidence row below corresponds to something the results document records. The
    ``observation`` strings quote or paraphrase it, the producers are the runs it names, and
    nothing is asserted that the document does not support -- including the two requirements
    it says nothing about.
    """
    history = assert_history(root)
    digest = str(work_digest or beacon_work_digest(root))
    state: dict[str, Any] = {
        "schema_version": 1,
        "run_id": "ar223-beacon",
        "project": "ariadne",
        "source_document": history["path"],
    }
    record = contract.create(
        state,
        text=BEACON_REQUEST,
        task_id="ar223-beacon",
        source_refs=[history["path"]],
        constraints=["no Boreal changes", "no release"],
        non_goals=["visual acceptance claimed by the engine", "human acceptance granted by the engine"],
    )
    contract_id = str(record["contract_id"])
    revision = str(record.get("revision", ""))

    surface = requirements.create(
        state,
        contract_id=contract_id,
        text="the Beacon surface renders at the default viewport and the capture is bound to the observed work digest",
        kind="VISUAL",
        scope_paths=["src/styles/app.css", "src/**/*.tsx"],
        task_id="ar223-beacon",
        rationale="a screenshot with no digest binding establishes nothing about this revision",
    )
    mechanical = requirements.create(
        state,
        contract_id=contract_id,
        text="the project typechecks and builds",
        kind="CONSTRAINT",
        task_id="ar223-beacon",
        rationale="a build result establishes a build requirement and nothing wider",
    )
    regression = requirements.create(
        state,
        contract_id=contract_id,
        text="the project's own test suite passes",
        kind="REGRESSION",
        task_id="ar223-beacon",
    )
    responsive = requirements.create(
        state,
        contract_id=contract_id,
        text="the log table does not clip or overflow below 768px",
        kind="VISUAL",
        scope_paths=["src/styles/app.css", "src/components/LogTable.tsx"],
        task_id="ar223-beacon",
        rationale="AR-222 measured exactly this and it is the finding that stayed major",
    )
    keyboard = requirements.create(
        state,
        contract_id=contract_id,
        text="the navigation is reachable and dismissible with the keyboard alone",
        kind="INTERACTION",
        scope_paths=["src/components/Nav.tsx"],
        task_id="ar223-beacon",
        rationale="needs an interaction trace; a build result and a screenshot cannot establish it",
    )
    hierarchy = requirements.create(
        state,
        contract_id=contract_id,
        text="the heading hierarchy reads coherently to a human reviewer",
        kind="SUBJECTIVE",
        origin="DERIVED",
        blocking=False,
        human_gate=True,
        task_id="ar223-beacon",
        rationale=(
            "AR-222 states its critique does not judge hierarchy, density or composition, so this is "
            "a derived reading rather than something the request asked for and not something the "
            "engine may settle"
        ),
    )

    ids = {
        "surface": str(surface["requirement_id"]),
        "mechanical": str(mechanical["requirement_id"]),
        "regression": str(regression["requirement_id"]),
        "responsive": str(responsive["requirement_id"]),
        "keyboard": str(keyboard["requirement_id"]),
        "hierarchy": str(hierarchy["requirement_id"]),
    }

    evidence.record(
        state,
        kind="RENDER",
        stance="SUPPORTS",
        producer="ar222-capture",
        producer_role="evidence_producer",
        producer_execution="ar222-capture-run",
        observation=(
            "six captures per pass at 1440x900, including the focused control states; the results "
            "document records the capture as bound to the observed work digest"
        ),
        requirement_ids=[ids["surface"]],
        work_digest=digest,
        contract_revision=revision,
        contract_id=contract_id,
        task_id="ar223-beacon",
        viewport="1440x900",
        source_kind="ENGINE_RECORD",
        artifact_path=history["path"],
        source_record_id=history["path"],
    )
    evidence.record(
        state,
        kind="BUILD",
        stance="SUPPORTS",
        producer="ar222-mechanical-validation",
        producer_role="evidence_producer",
        producer_execution="ar222-mechanical-run",
        observation=(
            "npm run typecheck and npm run build passed in both passes; 9.125s of mechanical "
            "validation in total across before and after"
        ),
        requirement_ids=[ids["mechanical"]],
        work_digest=digest,
        contract_revision=revision,
        contract_id=contract_id,
        task_id="ar223-beacon",
        source_kind="ENGINE_RECORD",
        artifact_path=history["path"],
    )
    evidence.record(
        state,
        kind="TEST",
        stance="SUPPORTS",
        producer="ar222-mechanical-validation",
        producer_role="evidence_producer",
        producer_execution="ar222-mechanical-run",
        observation="npm test passed in both the before and the after pass",
        requirement_ids=[ids["regression"]],
        work_digest=digest,
        contract_revision=revision,
        contract_id=contract_id,
        task_id="ar223-beacon",
        source_kind="ENGINE_RECORD",
        artifact_path=history["path"],
    )
    evidence.record(
        state,
        kind="RENDER",
        stance="CONTRADICTS",
        producer="ar222-independent-critique",
        producer_role="independent_reviewer",
        producer_execution="ar222-critique-run",
        observation=(
            "at 390px the log table reaches 568px; the method and path columns are cut off and "
            "unreachable. Persistent after one bounded repair, improving from 12 clipped elements "
            "to 5"
        ),
        requirement_ids=[ids["responsive"], ids["hierarchy"]],
        work_digest=digest,
        contract_revision=revision,
        contract_id=contract_id,
        task_id="ar223-beacon",
        viewport="390x844",
        external=False,
        source_kind="ENGINE_RECORD",
        artifact_path=history["path"],
    )
    evidence.record(
        state,
        kind="REVIEW",
        stance="PARTIALLY_SUPPORTS",
        producer="ar222-independent-critique",
        producer_role="independent_reviewer",
        producer_execution="ar222-critique-run",
        observation=(
            "the focus indication reading was an artifact of an inspection-before-capture defect; "
            "the re-run found the focused control has a clear focus ring"
        ),
        requirement_ids=[ids["keyboard"]],
        work_digest=digest,
        contract_revision=revision,
        contract_id=contract_id,
        task_id="ar223-beacon",
        source_kind="ENGINE_RECORD",
        artifact_path=history["path"],
    )
    claims.extract(
        state,
        actor="ar221-implementer",
        statement=(
            "The responsive layout is fixed: the log table no longer clips below 768px."
        ),
        origin="PROSE",
        contract_id=contract_id,
        work_digest=digest,
        actor_execution="ar221-implementation-run",
        actor_role="implementation_worker",
        requirement_scope=[
            dict(row) for row in requirements.requirements_for_contract(state, contract_id)
        ],
        task_id="ar223-beacon",
        source_label="controlled fixture claim: AR-222 recorded no such claim",
    )
    state["beacon"] = {
        "contract_id": contract_id,
        "contract_revision": revision,
        "requirement_ids": ids,
        "work_digest": digest,
        "history": history,
    }
    return state


def beacon_pass(
    state: dict,
    *,
    independent_review: Mapping[str, Any] | None = None,
) -> dict:
    """Run the real proof pass over the Beacon state and return the acceptance record."""
    block = dict(state.get("beacon", {}))
    review = dict(independent_review or {"reviewer": "ar222-independent-critique", "role": "independent_reviewer"})
    record = gates.run_pass(
        state,
        contract_id=str(block["contract_id"]),
        work_digest=str(block.get("work_digest", "")),
        task_id="ar223-beacon",
        pass_kind="INITIAL",
        independent_review=review,
        require_independent_review=True,
        require_human_acceptance=False,
    )
    return record


# ------------------------------------------------------------------ repair and re-verify

REPAIR_WORK_DIGEST = "4b19c0a7e52d3f68"
REPAIRED_WORK_DIGEST = "9c05ae31d74b8620"
"""Two revisions of one controlled fixture, so the repair changes the digest for real."""

PARSER_FINGERPRINT = "3c81f0a5d7e2496b17ad4c0e9f5312ab8d67e04c1f9a2b5d8e03746c1a9f2b0d"
"""The parser's own revision, pinned by the requirement that depends on it.

A fixture value standing in for a real file digest. Its purpose is to be *checked*: the
re-verification pass compares it against what the repository currently holds, and a requirement
that declared nothing could only ever come back ``UNKNOWN`` no matter how unrelated the change
was.
"""

REPAIR_REQUEST = "Collapse the sidebar below 900px without changing how the parser reads input."

INTERACTION_CHECK = {
    "check_id": "sidebar-collapse-interaction",
    "kind": "INTERACTION",
    "requirement_ids": [],
    "cost": "CHEAP",
    "method": "drive the toggle at 880px and assert the sidebar collapses",
}
PARSER_CHECK = {
    "check_id": "parser-bare-list",
    "kind": "TEST",
    "requirement_ids": [],
    "cost": "CHEAP",
    "method": "pytest tests/test_parser.py -q",
}


def repair_state() -> dict:
    """A controlled fixture with one failing requirement and one unrelated passing one.

    Two requirements rather than one, because a repair demonstration that only ever touches the
    requirement that failed is indistinguishable from re-running everything and hoping. The
    parser requirement is included so the selective half of re-verification is observable: after
    the repair it keeps its evidence and is never re-checked.
    """
    state: dict[str, Any] = {"schema_version": 1, "run_id": "ar223-repair", "project": "ariadne"}
    record = contract.create(
        state,
        text=REPAIR_REQUEST,
        task_id="ar223-repair",
        source_refs=["controlled fixture: ar223-repair"],
        non_goals=["redesign the navigation", "change parser behaviour"],
    )
    contract_id = str(record["contract_id"])
    revision = str(record.get("revision", ""))
    sidebar = requirements.create(
        state,
        contract_id=contract_id,
        text="the sidebar collapses below 900px",
        kind="INTERACTION",
        scope_paths=["src/components/Sidebar.tsx"],
        task_id="ar223-repair",
    )
    parser = requirements.create(
        state,
        contract_id=contract_id,
        text="the parser still accepts a bare list argument",
        kind="REGRESSION",
        scope_paths=["src/parser.py"],
        dependencies={"src/parser.py": PARSER_FINGERPRINT},
        task_id="ar223-repair",
        rationale=(
            "declares the fingerprint of the file it depends on, which is the only thing that lets "
            "the invalidation pass prove it unaffected rather than guess that it is"
        ),
    )
    ids = {"sidebar": str(sidebar["requirement_id"]), "parser": str(parser["requirement_id"])}
    evidence.record(
        state,
        kind="INTERACTION",
        stance="CONTRADICTS",
        producer="ar223-interaction-driver",
        producer_role="evidence_producer",
        producer_execution="ar223-interaction-pass1",
        observation="at 880px the toggle was pressed and the sidebar stayed open at its full width",
        requirement_ids=[ids["sidebar"]],
        work_digest=REPAIR_WORK_DIGEST,
        contract_revision=revision,
        contract_id=contract_id,
        task_id="ar223-repair",
        viewport="880x900",
        source_kind="HUMAN_OBSERVATION",
        source_record_id="controlled fixture: ar223-repair interaction pass 1",
    )
    evidence.record(
        state,
        kind="TEST",
        stance="SUPPORTS",
        producer="ar223-engine-suite",
        producer_role="evidence_producer",
        producer_execution="ar223-parser-pass1",
        observation="tests/test_parser.py passed on a bare list argument",
        requirement_ids=[ids["parser"]],
        work_digest=REPAIR_WORK_DIGEST,
        contract_revision=revision,
        contract_id=contract_id,
        task_id="ar223-repair",
        source_kind="CI_RUN",
        source_record_id="controlled fixture: ar223-repair parser pass 1",
    )
    state["repair"] = {
        "contract_id": contract_id,
        "contract_revision": revision,
        "requirement_ids": ids,
        "changed": ["src/components/Sidebar.tsx"],
        "before_digest": REPAIR_WORK_DIGEST,
        "after_digest": REPAIRED_WORK_DIGEST,
    }
    return state


def repair_slices(state: dict) -> dict:
    """Pass 1, the repair, the selective invalidation, the targeted plan, and pass 2.

    The order is the demonstration. Pass 1 fails on the interaction. The edit changes the
    work digest, which makes the pass-1 evidence stale for the sidebar and leaves the parser's
    evidence current, because the parser's declared scope does not include the file that
    changed. The plan then selects the one check that covers the stale blocking requirement,
    and pass 2 proves the sidebar without re-running the parser suite.
    """
    block = dict(state.get("repair", {}))
    contract_id = str(block["contract_id"])
    ids = dict(block["requirement_ids"])
    first = gates.run_pass(
        state,
        contract_id=contract_id,
        work_digest=REPAIR_WORK_DIGEST,
        task_id="ar223-repair",
        pass_kind="INITIAL",
        independent_review={"reviewer": "ar223-independent-reviewer"},
    )
    after = invalidation.invalidate(
        state,
        contract_id=contract_id,
        changed=list(block["changed"]),
        current_dependencies={"src/parser.py": PARSER_FINGERPRINT},
    )
    stale = [str(item) for item in after.get("stale", [])] + [
        str(item) for item in after.get("unknown", []) if str(item) in ids.values()
    ]
    plan = invalidation.plan(
        stale_requirement_ids=stale,
        checks=[
            invalidation.check(
                check_id=INTERACTION_CHECK["check_id"],
                kind=INTERACTION_CHECK["kind"],
                requirement_ids=[ids["sidebar"]],
                cost=INTERACTION_CHECK["cost"],
                method=INTERACTION_CHECK["method"],
            )
        ],
        blocking_ids=[ids["sidebar"]],
    )
    evidence.record(
        state,
        kind="INTERACTION",
        stance="SUPPORTS",
        producer="ar223-interaction-driver",
        producer_role="evidence_producer",
        producer_execution="ar223-interaction-pass2",
        observation="at 880px the toggle collapsed the sidebar to its narrow state after the repair",
        requirement_ids=[ids["sidebar"]],
        work_digest=REPAIRED_WORK_DIGEST,
        contract_revision=str(block["contract_revision"]),
        contract_id=contract_id,
        task_id="ar223-repair",
        viewport="880x900",
        source_kind="HUMAN_OBSERVATION",
        source_record_id="controlled fixture: ar223-repair interaction pass 2",
    )
    second = gates.run_pass(
        state,
        contract_id=contract_id,
        work_digest=REPAIRED_WORK_DIGEST,
        task_id="ar223-repair",
        pass_kind="REVERIFICATION",
        supersedes_pass_id=str(first.get("pass_id", "")),
        repair_ids=["ar223-repair-1"],
        independent_review={"reviewer": "ar223-independent-reviewer"},
        unaffected=list(after.get("unaffected", [])),
    )
    return {
        "repair_version": BEACON_VERSION,
        "pass_one": first,
        "invalidation": after,
        "stale_requirement_ids": stale,
        "plan": plan,
        "pass_two": second,
        "lineage": gates.lineage(state, ids["sidebar"]),
        "parser_rerun": ids["parser"] in stale,
        "parser_evidence_readmitted": list(second.get("admitted_by_dependency_proof", [])),
        "note": (
            "the parser requirement was never stale and its check was never selected again; its "
            "pass-one evidence was readmitted at the new work digest on the strength of a declared "
            "dependency fingerprint rather than a fresh run. A repair demonstration that re-runs "
            "the whole suite proves nothing about Context Economics"
        ),
    }


def describe() -> dict:
    return {
        "version": BEACON_VERSION,
        "results_document": str(RESULTS_DOCUMENT).replace("\\", "/"),
        "markers_required": list(REQUIRED_MARKERS),
        "beacon": (
            "real preserved history: the responsive requirement FAILED, the keyboard requirement "
            "is UNPROVEN, the hierarchy requirement needs a human, and a fixture-supplied worker "
            "claim of completion is CONTRADICTED by the measurement that already exists"
        ),
        "repair": (
            "controlled fixture: FAILED, repair, changed work digest, stale evidence, one targeted "
            "check, PROVEN, with the unrelated requirement never re-checked"
        ),
        "authorization_effect": "none",
    }


__all__ = [
    "BEACON_VERSION",
    "BEACON_WORK_DIGEST_PREFIX",
    "REQUIRED_MARKERS",
    "RESULTS_DOCUMENT",
    "REPAIRED_WORK_DIGEST",
    "REPAIR_WORK_DIGEST",
    "assert_history",
    "beacon_pass",
    "beacon_state",
    "decisions",
    "describe",
    "repair_slices",
    "repair_state",
]