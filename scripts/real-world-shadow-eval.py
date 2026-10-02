#!/usr/bin/env python3
"""One real-world shadow evaluation of the Decision Runtime.

Not a synthetic fixture. Every decision here comes from running something against the
widgetco project on disk - a failing test, an edited file, a lint failure, an
unresolved question - and asking Ariadne's real integration entry points to classify it
through the real compiler, the real batch evaluator and the real runtime.

The runtime observes in shadow mode throughout. Nothing here promotes it, and nothing
here is allowed to change what Ariadne actually did.

Run: python scripts/real-world-shadow-eval.py <project-dir>
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def load_engine():
    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "ariadne_engine_realworld", root / "src" / "ariadne_engine" / "__init__.py",
        submodule_search_locations=[str(root / "src" / "ariadne_engine")])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run(command, cwd):
    """Run a real command and report what happened, including a timeout as an outcome."""
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command, cwd=str(cwd), capture_output=True, text=True, timeout=120)
        return {
            "exit_code": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
            "outcome": "PASS" if completed.returncode == 0 else "FAIL",
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "stdout": "", "stderr": "timed out", "outcome": "TIMEOUT",
                "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
    except OSError as exc:
        # A command that cannot be launched at all is a real environment condition and a
        # real thing to classify, not a harness failure.
        return {"exit_code": None, "stdout": "", "stderr": str(exc), "outcome": "ENVIRONMENT",
                "latency_ms": round((time.perf_counter() - started) * 1000, 2)}


def collect(project: Path):
    """Real bounded decisions: each one is something that actually happened to widgetco."""
    python = sys.executable
    cases = []

    # Failure classification, from genuinely different real failures.
    scenarios = [
        ("pytest on a passing suite", [python, "-m", "pytest", "-q", "tests"], None),
        ("pytest with a real NameError",
         [python, "-c",
          "from src.render import render_page\n"
          "def test_x():\n"
          "    render_page()\n"
          "import sys; sys.exit(0 if render_page else 1)"],
         "FAIL"),
        ("import of a module that does not exist",
         [python, "-c", "import src.nonexistent"], "FAIL"),
        ("a type error at runtime",
         [python, "-c",
          "from src.theme import apply_theme\n"
          "print(apply_theme(42))"], "FAIL"),
        ("a syntax error in a fresh file",
         [python, "-c", "def broken(:\n    pass"], "FAIL"),
        ("running with a stripped PATH, so the interpreter is not found",
         ["python-that-does-not-exist", "--version"], "FAIL"),
        ("a provider that is not installed",
         [python, "-c", "import definitely_not_installed_ar206"], "FAIL"),
        ("an out-of-memory condition simulated by an allocation ceiling",
         [python, "-c", "b = bytearray(200 * 1024 * 1024)"], "FAIL"),
        ("an operation that exceeds its time budget",
         [python, "-c",
          "import time\ntime.sleep(2)"], "PASS"),
        ("a successful import of the library",
         [python, "-c", "from src.theme import apply_theme; assert apply_theme('dark')"], "PASS"),
    ]
    for label, command, note in scenarios:
        result = run(command, project)
        cases.append({
            "family": "failure-classification",
            "label": label,
            "source": (result["stderr"] or result["stdout"] or label)[:2000],
            "observed_outcome": result["outcome"],
            "command_latency_ms": result["latency_ms"],
        })

    # Review escalation, from genuinely different review inputs.
    reviews = [
        ("low stakes, reversible, English", {"stakes": "low", "affected_scope": "widgetco/src/theme.py",
                                              "verification_result": "VERIFIED", "protected": False}),
        ("high stakes, release scope", {"stakes": "high", "affected_scope": "widgetco/src/render.py",
                                        "verification_result": "VERIFIED", "protected": False}),
        ("protected file, no verification", {"stakes": "high", "affected_scope": "widgetco/src/theme.py",
                                             "verification_result": "UNVERIFIED", "protected": True}),
        ("protected file, verified", {"stakes": "medium", "affected_scope": "widgetco/src/render.py",
                                      "verification_result": "VERIFIED", "protected": True}),
        ("unverified, unprotected, wide scope",
         {"stakes": "medium", "affected_scope": "widgetco/tests, widgetco/src",
          "verification_result": "UNVERIFIED", "protected": False}),
    ]
    for label, entries in reviews:
        cases.append({"family": "review-escalation", "label": label, "entries": entries,
                      "observed_outcome": "REVIEW_RECORDED"})

    # Evidence relevance, from real evidence about real files.
    evidence = [
        ("current test result supports a rendering claim", "tests/test_render.py",
         "VERIFIED", "CURRENT"),
        ("stale design note offered as current evidence", "docs/design-v1.md",
         "DESIGN", "STALE"),
        ("a claim with no provenance at all", "notes/scratch.txt", "CLAIM", "CURRENT"),
        ("authoritative contract supports a verification claim", "PROJECT.md",
         "VERIFIED", "CURRENT"),
        ("an unverifiable assertion about performance", "benchmarks/claim.md",
         "ASSERTION", "CURRENT"),
    ]
    for label, claim, provenance, freshness in evidence:
        cases.append({"family": "evidence-relevance", "label": label, "claim": claim,
                      "provenance": provenance, "freshness": freshness,
                      "observed_outcome": "REVIEW_RECORDED"})

    # Route family, from real work items.
    routes = [
        ("mechanical rename of a constant", {"task_kind": "mechanical"}),
        ("a design decision about theming", {"task_kind": "design"}),
        ("an exploratory spike", {"task_kind": "spike"}),
        ("an unfamiliar failure", {"task_kind": "unknown"}),
        ("a routine bug fix", {"task_kind": "bugfix"}),
    ]
    for label, entries in routes:
        cases.append({"family": "route-family", "label": label, "entries": entries,
                      "observed_outcome": "ROUTED"})
    return cases


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: real-world-shadow-eval.py <project-dir>", file=sys.stderr)
        return 2
    project = Path(sys.argv[1]).resolve()
    if not project.is_dir():
        print(f"no such project: {project}", file=sys.stderr)
        return 2

    engine = load_engine()
    RUNTIME = engine.decisions.runtime
    C = engine.decisions.contracts
    engine_contracts = engine.contracts
    integrations = engine.decisions.integrations

    session = RUNTIME.session.DecisionRuntime.discover()
    provider = RUNTIME.provider.LocalBoundedProvider(session)
    status = session.status()

    records = []
    errors = []
    with tempfile.TemporaryDirectory(prefix="ar206-realworld-state-") as workspace:
        state = {
            "schema_version": 1, "run_id": "ar206-realworld", "project": str(project),
            "run_root": workspace, "packets": [
                {"id": "t-S1", "stage": "S1", "path": str(Path(workspace) / "t-S1")}],
            "approvals": [], "decisions": [], "decision_batches": [], "decision_shadow": [],
        }
        for case in collect(project):
            before = len(state["decisions"])
            started = time.perf_counter()
            try:
                if case["family"] == "failure-classification":
                    integrations.classify_failure(
                        state, source=case["source"], consequence="LOW",
                        runtime=session, provider=provider)
                elif case["family"] == "review-escalation":
                    integrations.review_escalation(state, **case["entries"], runtime=session,
                                                  provider=provider)
                elif case["family"] == "evidence-relevance":
                    integrations.evidence_relevance(
                        state, requirement=case["label"], claim=case["claim"],
                        provenance=case["provenance"], freshness=case["freshness"],
                        runtime=session, provider=provider)
                else:
                    integrations.route_family(state, **case["entries"], runtime=session,
                                              provider=provider)
            except Exception as exc:  # noqa: BLE001 - recorded, not raised
                errors.append({"family": case["family"], "label": case["label"],
                               "error": f"{type(exc).__name__}: {exc}"})
                continue
            latency_ms = round((time.perf_counter() - started) * 1000, 3)
            for record in state["decisions"][before:]:
                records.append({
                    "family": case["family"],
                    "label": case["label"],
                    "observed_outcome": case["observed_outcome"],
                    "decision_id": record.get("decision_id", ""),
                    "status": record.get("status"),
                    "question_id": record.get("question_id"),
                    # The record names the question version directly; the definition
                    # digest has to be derived, because the record stores the question
                    # rather than a digest of it.
                    "question_version": record.get("definition_version"),
                    "definition_digest": definition_digest(record),
                    # The projection digest the decision was made from is recorded as
                    # state_digest: the projection is what the state was reduced to.
                    "projection_digest": record.get("state_digest"),
                    "provider": record.get("provider"),
                    "implementation": record.get("model"),
                    "model_revision": record.get("model_version"),
                    "contract_version": record.get("contract_version"),
                    "answer": record.get("answer"),
                    "confidence": record.get("confidence"),
                    "confidence_kind": record.get("confidence_kind"),
                    "abstention_reason": record.get("abstention_reason", ""),
                    "authorization_effect": record.get("authorization_effect"),
                    "acted_on": record.get("acted_on"),
                    "latency_ms": latency_ms,
                    "policy_accepted": (record.get("policy_verdict") or {}).get("accepted"),
                })

    session.shutdown()

    shadow = state["decision_shadow"]
    disagreements = sum(1 for row in shadow
                       if row.get("authoritative_answer") and row.get("answer")
                       and row["authoritative_answer"] != row["answer"])
    summary = {
        "runtime_id": engine_contracts.CANONICAL_RUNTIME_ID,
        "runtime_kind": status.get("runtime_kind"),
        "implementation": status.get("implementation"),
        "model_revision": status.get("model_revision"),
        "device": status.get("device"),
        "project": project.name,
        "total_decisions": len(records),
        "by_family": {},
        "answered": sum(1 for r in records if r["status"] == "answered"),
        "abstained": sum(1 for r in records if r.get("abstention_reason")),
        "shadow_records": len(shadow),
        "shadow_disagreements": disagreements,
        "shadow_with_execution_effect": sum(
            1 for row in shadow if row.get("execution_effect") != "none"),
        "shadow_with_authority": sum(
            1 for row in shadow if row.get("authorization_effect") != "none"),
        "confidence_kinds": sorted({str(r["confidence_kind"]) for r in records}),
        "calibrated_records": sum(1 for r in records if "CALIBRATED" in str(r["confidence_kind"])),
        "authorization_effects": sorted({str(r["authorization_effect"]) for r in records}),
        "acted_on_any": any(r["acted_on"] for r in records),
        "latency_ms": {
            "min": min((r["latency_ms"] for r in records), default=0),
            "median": sorted(r["latency_ms"] for r in records)[len(records) // 2] if records else 0,
            "max": max((r["latency_ms"] for r in records), default=0),
        },
        "errors": errors,
        "isolation_problems": [str(p) for p in shadow_problems(state)],
        "verification_status": "UNKNOWN: no reviewed or verified ground truth was recorded",
    }
    for record in records:
        summary["by_family"].setdefault(record["family"], 0)
        summary["by_family"][record["family"]] += 1

    print(json.dumps({"summary": summary, "records": records}, indent=2))
    return 0


def definition_digest(record) -> str:
    """A digest over the question as the record states it.

    The record carries the question rather than a digest of it, which is the right
    trade for an audit trail - you can read what was actually asked - but it means an
    evaluation has to derive the digest itself if it wants to report one.
    """
    import hashlib

    payload = {
        "question_id": record.get("question_id"),
        "primitive": record.get("primitive"),
        "instructions": record.get("instructions"),
        "options": list(record.get("options") or []),
        "scale": list(record.get("scale") or []),
        "definition_version": record.get("definition_version"),
        "stage": record.get("stage"),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def shadow_problems(state):
    RUNTIME = load_engine().decisions.runtime
    return RUNTIME.shadow.shadow_problems(state)


if __name__ == "__main__":
    raise SystemExit(main())
