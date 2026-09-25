"""Fixture documents and options for the AR-200 benchmark.

Reuse rule from the AR-200 brief: prefer the runtime's own fixtures. The
canonical handoff / return / review fixtures below are taken verbatim from the
runtime's self-test generators (scripts/ariadne.py::filled_handoff,
filled_return, filled_review) through the imported module, so the benchmark
cannot drift away from the runtime's own fixture contract.
"""

from __future__ import annotations

import json
from pathlib import Path

from .driver import Repo, Sandbox


# ---------------------------------------------------------------- project docs

def project_md(thesis_criterion: str = "The interaction has a clear response.") -> str:
    return (
        "# PROJECT\n\n## Goal\n\nTest a typographic interaction.\n\n"
        "## Design thesis\n\n"
        "**A speaking line makes sound visible through one typographic gesture.**\n\n"
        "## Accepted patterns\n\n| Pattern | Reason | Rationale type |\n|---|---|---|\n\n"
        f"## Success criteria\n\n1. {thesis_criterion}\n\n"
        "## Open questions\n\nNone.\n"
    )


def agents_md(stage: str = "S1", gate: str = "none", next_prompt: str = "prompts/design-direction.md") -> str:
    return (
        "## Current state\n\n"
        f"| **Stage** | `{stage}` |\n"
        f"| **Last gate passed** | `{gate}` |\n"
        f"| **Next prompt** | `{next_prompt}` |\n"
    )


def design_md(status: str = "draft - awaiting G1") -> str:
    """A workflow-complete DESIGN.md.

    The design-quality contract (``creative-intelligence.design_quality_problems``)
    requires a named tension, a concrete signature moment with a mobile
    equivalent, at least three project-specific rejections and an affirmative
    ten-row G1 direction check. AR-201 enforces that contract before the
    direction can pass G1 on *every* continuation path, so the shared fixture
    carries it instead of relying on the old stage-result bypass.
    """
    thesis = "**A speaking line makes sound visible through one typographic gesture.**"
    body = (
        "# DESIGN\n\n"
        f"**Status:** {status}\n\n"
        "## Design thesis\n\n" + thesis + "\n\n"
        "**The tension:** archival but immediate.\n\n"
        "## Signature moment\n\n"
        "- **What / where:** A speaking line crosses the listening boundary.\n"
        "- **Why memorable:** Sound becomes a typographic gesture.\n"
        "- **Mobile equivalent:** The line becomes a vertical sound trace.\n\n"
        "## Responsive behaviour\n\n"
        "| Width | Composition |\n|---|---|\n"
        "| 375 | The line becomes a vertical sound trace. |\n"
        "| 1280 | The line crosses the listening boundary. |\n\n"
        "## Asset direction\n\n"
        "| Asset | Exists? | Plan | Blocking? |\n|---|---|---|---|\n"
        "| none | yes | no asset required | no |\n\n"
        "## Anti-patterns for this project\n\n"
        "1. Do not add a waveform visualiser; it is the generic shorthand for sound.\n"
        "2. Do not animate the whole line; the gesture is the boundary crossing only.\n"
        "3. Do not introduce a second accent colour; one gesture carries the meaning.\n\n"
        "## G1 direction check\n\n"
        "| # | Check | Y/N | If no, why not |\n|---|---|---|---|\n"
        "| 1 | Thesis tells you what to do about a hero image | y | |\n"
        "| 2 | No banned mood words | y | |\n"
        "| 3 | Type ratio at least 4x | y | |\n"
        "| 4 | Palette has a stated source | y | |\n"
        "| 5 | Motion has one of the five purposes | y | |\n"
        "| 6 | Signature moment named, with a mobile equivalent | y | |\n"
        "| 7 | Three or more specific rejections | y | |\n"
        "| 8 | All asset dependencies resolved | y | |\n"
        "| 9 | Survives the swap test | y | |\n"
        "| 10 | Closest anti-generic row named, and why it is not that | y | |\n"
    )
    return body


def qa_md() -> str:
    return (
        "# QA\n\n## Mechanical\n\n| # | Check | Result | Evidence |\n|---|---|---|---|\n"
        "| 1 | Build | pass | fixture |\n\n## Judgement\n\nPending.\n\n"
        "## Screenshots\n\n| View | Path |\n|---|---|\n| Fixture | none |\n"
    )


# ------------------------------------------------------- runtime-owned fixtures

def runtime_fixtures(repo: Repo) -> dict:
    """Load the runtime's own fixture generators (no side effects, no bytecode)."""
    module = repo.module("ariadne.py")
    return {
        "handoff": module.filled_handoff,
        "return_handoff": module.filled_return,
        "review": module.filled_review,
        "module": module,
    }


# --------------------------------------------------------------------- helpers

OPERATOR_IDENTITY = "benchmark-operator"
REVIEWER_IDENTITY = "benchmark-independent-reviewer"


def creative_assessment(repo: Repo) -> dict:
    """The runtime's own low-risk assessment (no model, no network)."""
    return repo.module("creative-intelligence.py").low_assessment()


def establish_creative_plan(repo: Repo, box: Sandbox) -> None:
    """Record the project's internal creative plan while the run is still at S1."""
    source = box.root / "creative-assessment.json"
    source.write_text(json.dumps(creative_assessment(repo), indent=2) + "\n", encoding="utf-8")
    return repo.cli("creative-plan", "--run-root", str(box.run_root), "--input", str(source))


def record_direction_evidence(repo: Repo, box: Sandbox) -> None:
    """Record the S3 design-direction work with real, project-local artifacts."""
    evidence = box.write(
        ".ariadne/creative/design-direction-invocation.md",
        "# Design direction work log\n\nFixture record of the S3 direction work.\n",
    )
    source = box.root / "creative-events.json"
    source.write_text(json.dumps({
        "events": [
            {"type": "skill", "skill": "design-direction", "state": "invoked",
             "evidence_path": str(evidence)},
            {"type": "skill", "skill": "design-direction", "state": "completed",
             "output_path": str(box.path("DESIGN.md")),
             "result": "Design direction recorded in DESIGN.md.", "usefulness": "useful"},
            {"type": "direction", "id": "direction-a",
             "thesis": "A speaking line makes sound visible through one typographic gesture.",
             "mechanism": "A single line crosses a listening boundary.",
             "experience": "The page answers only while someone speaks.",
             "status": "selected"},
        ]
    }, indent=2) + "\n", encoding="utf-8")
    return repo.cli("record-creative", "--run-root", str(box.run_root), "--input", str(source))


def start_s1(repo: Repo, box: Sandbox, *, request: str = "Build a small typographic experiment.",
             extra: list[str] | None = None):
    """Start a run at S1 with an explicit run root inside the sandbox."""
    return repo.cli("start", "--project", str(box.project), "--run-root", str(box.run_root),
                    "--run-id", "bench", "--request", request, *(extra or []))


def complete_s1(repo: Repo, box: Sandbox, fixtures: dict) -> None:
    """Write the S1 outputs, record the structural stage result, select the creative work.

    AR-201 requires the creative plan before the direction can pass G1 on any
    path, so a workflow-complete S1 fixture establishes it here (the runtime
    also documents this order: planning belongs immediately after the brief).
    """
    box.write("PROJECT.md", project_md())
    box.write("AGENTS.md", agents_md("S1", "none", "prompts/design-direction.md"))
    repo.cli("record-result", "--run-root", str(box.run_root), "--status", "complete",
             "--provider", "benchmark-fixture", "--model", "none",
             "--summary", "S1 brief complete (benchmark fixture)",
             "--file", "PROJECT.md", "--file", "AGENTS.md")
    establish_creative_plan(repo, box)


def to_s3(repo: Repo, box: Sandbox):
    """Advance the run from S1 to a prepared S3 packet."""
    return repo.cli("prepare-next", "--run-root", str(box.run_root), "--motion", "no", "--assets", "no")


def lock_g1(box: Sandbox, repo: Repo | None = None, *, identity: str = OPERATOR_IDENTITY):
    """Complete the direction work and record the human G1 approval through the engine.

    The pre-AR-201 fixture wrote ``DESIGN.md``/``AGENTS.md`` gate fields by hand and
    the runtime read them as authority (the confirmed defect). The approval is now
    an engine record on the human channel; the document fields are mirrors the
    engine writes for humans.
    """
    repo = repo or box.repo
    if repo is None:
        raise AssertionError("lock_g1 needs a repo handle (pass one or use Ctx.sandbox)")
    box.write("DESIGN.md", design_md("locked at G1 on 2026-09-22"))
    box.write("AGENTS.md", agents_md("S3", "G1", "prompts/build-kickoff.md"))
    record_direction_evidence(repo, box)
    return record_g1_approval(box, repo, identity=identity)


def record_g1_approval(box: Sandbox, repo: Repo | None = None, *, identity: str = OPERATOR_IDENTITY):
    """Record only the human G1 decision, leaving the direction's creative evidence as it is.

    Used to isolate the creative-evidence precondition from the authorization
    precondition: with the approval present, the only thing that can stop the S3
    to S4A transition on any path is the missing direction evidence.
    """
    repo = repo or box.repo
    if repo is None:
        raise AssertionError("record_g1_approval needs a repo handle (pass one or use Ctx.sandbox)")
    return repo.cli("approve-gate", "--run-root", str(box.run_root), "--gate", "G1",
                    "--identity", identity,
                    "--note", "Benchmark fixture: the human operator locks the direction.")


def record_g3(repo: Repo, box: Sandbox, *, identity: str = OPERATOR_IDENTITY):
    """Record the human G3 approval for the review currently on the boundary."""
    return repo.cli("approve-gate", "--run-root", str(box.run_root), "--gate", "G3",
                    "--identity", identity,
                    "--note", "Benchmark fixture: the human accepts the reviewed revision.")


def ingest_independent_review(repo: Repo, box: Sandbox, source, *,
                              identity: str = REVIEWER_IDENTITY, kind: str | None = None):
    """Ingest a review judgement with an explicit reviewer identity."""
    argv = ["ingest-review", "--run-root", str(box.run_root), "--input", str(source),
            "--reviewer-identity", identity]
    if kind:
        argv += ["--kind", kind]
    return repo.cli(*argv)


def write_handoff(box: Sandbox, fixtures: dict) -> None:
    box.write("HANDOFF.md", fixtures["handoff"]())


def record_skill_evidence(repo: Repo, box: Sandbox, *, skill: str, output_relative: str,
                          result: str, events_name: str | None = None) -> None:
    """Record one selected creative skill's execution exactly as a live session would.

    AR-202 requires evidence, not a claim: the S4A implementation-planning skill and
    the S4B QA skill are continuation preconditions, so their execution is recorded
    through the same ``record-creative`` contract a project uses.
    """
    source = box.root / (events_name or f"{skill.lower().replace(' ', '-')}-events.json")
    source.write_text(json.dumps({"events": [
        {"type": "skill", "skill": skill, "state": "invoked",
         "evidence_path": str(box.path(output_relative))},
        {"type": "skill", "skill": skill, "state": "completed",
         "output_path": str(box.path(output_relative)),
         "result": result, "usefulness": "useful"},
    ]}, indent=2) + "\n", encoding="utf-8")
    return repo.cli("record-creative", "--run-root", str(box.run_root), "--input", str(source))


def record_implementation_evidence(repo: Repo, box: Sandbox):
    """Map every approved requirement to a recorded implementation.

    AR-202 requires the implementation trace at the review boundary. The fixture
    records it against the immutable HANDOFF.md, the artifact the build worked from.
    """
    if not box.exists(".ariadne/creative-operations.json"):
        return None
    ledger = json.loads(box.read(".ariadne/creative-operations.json"))
    requirements = [item for item in ledger.get("requirements", []) if item.get("id")]
    if not requirements:
        return None
    source = box.root / "implementation-events.json"
    source.write_text(json.dumps({"events": [
        {"type": "implementation", "requirement_id": item["id"], "status": "implemented",
         "summary": f"Fixture recorded the implementation of {item['id']} in the build.",
         "source_path": str(box.path("HANDOFF.md"))}
        for item in requirements
    ]}, indent=2) + "\n", encoding="utf-8")
    return repo.cli("record-operations", "--run-root", str(box.run_root), "--input", str(source))


def reach_s4a_with_handoff(repo: Repo, box: Sandbox, fixtures: dict) -> None:
    """Full deterministic path from S1 to a prepared S4A packet with a valid handoff."""
    start_s1(repo, box)
    complete_s1(repo, box, fixtures)
    to_s3(repo, box)
    lock_g1(box, repo)
    approve_s3_and_reach_s4a(repo, box)
    write_handoff(box, fixtures)
    box.write("AGENTS.md", agents_md("S4", "G1", "prompts/build-kickoff.md"))
    repo.cli("record-result", "--run-root", str(box.run_root), "--status", "complete",
             "--provider", "benchmark-fixture", "--model", "none",
             "--summary", "Implementation handoff complete",
             "--file", "HANDOFF.md", "--file", "AGENTS.md")
    record_skill_evidence(
        repo, box, skill="implementation-planning", output_relative="HANDOFF.md",
        result="The handoff became the bounded build context.",
        events_name="planning-events.json",
    )


def approve_s3_and_reach_s4a(repo: Repo, box: Sandbox):
    """Record the S3 stage result and continue to the approved S4A boundary.

    The G1 approval itself is recorded by :func:`lock_g1` through the engine, so
    this step only records the structural result and asks for the continuation.
    """
    repo.cli("record-result", "--run-root", str(box.run_root), "--status", "complete",
             "--provider", "benchmark-fixture", "--model", "none",
             "--summary", "Direction approved at G1", "--file", "DESIGN.md", "--file", "AGENTS.md")
    return repo.cli("prepare-next", "--run-root", str(box.run_root))


def clear_preflight_and_reach_s4b(repo: Repo, box: Sandbox):
    """Record provider preflight, prepare the S4B worker packet, return the Result."""
    repo.cli("preflight", "--run-root", str(box.run_root), "--availability", "available",
             "--quota", "sufficient")
    return repo.cli("prepare-next", "--run-root", str(box.run_root))


def prepare_s5(repo: Repo, box: Sandbox, target: str = "http://127.0.0.1:3000",
               lenses: str = "creative-director (light)"):
    """Prepare the isolated review boundary.

    The runtime deliberately requires both a review target and an explicit lens
    selection: neither is a transport default. AR-202 also requires the S4B skill
    evidence and the implementation trace, so the fixture records them here the way
    a live build session records them before the boundary closes.
    """
    if box.exists("QA.md"):
        record_skill_evidence(
            repo, box, skill="QA", output_relative="QA.md",
            result="Mechanical QA evidence was recorded for the reviewed revision.",
            events_name="qa-events.json",
        )
    record_implementation_evidence(repo, box)
    return repo.cli("prepare-next", "--run-root", str(box.run_root),
                    "--target", target, "--lenses", lenses)


def deliver_return(box: Sandbox, fixtures: dict, status: str = "complete") -> Path:
    """Write the structured return handoff to the packet's declared return target.

    A completed implementation boundary also carries mechanical QA evidence, so the
    fixture writes QA.md at the same time (the runtime requires it before S5).
    """
    manifest = box.manifest()
    target = manifest.get("return_target")
    if not target:
        raise AssertionError("S4B manifest has no return_target")
    packet_id = manifest["packet_id"]
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    Path(target).write_text(fixtures["return_handoff"](status, packet_id), encoding="utf-8")
    if status == "complete" and not box.exists("QA.md"):
        box.write("QA.md", qa_md())
    return Path(target)
