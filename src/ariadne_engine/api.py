"""Narrow programmatic API over the orchestration core.

Every function returns a :class:`Result` instead of printing: ``exit_code``
(0 success, 1 refusal/contract error, 2 paused/needs-human), the exact operator
text the CLI shows (``format_result``), the artifacts the operation named and
whether the run state changed. The CLI is a presentation layer over this
module, so the programmatic and command-line entry points cannot enforce
different rules.

Usage from a source checkout::

    import importlib.util
    spec = importlib.util.spec_from_file_location("ariadne_runtime", "scripts/ariadne.py")
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    result = runtime.ENGINE_API.status(run_root="...")
    print(runtime.ENGINE_API.format_result(result), end="")

Stability: the v2 product surface is classified in :mod:`ariadne_engine.public`.
Every function exported here is either STABLE_V2, PROVISIONAL or INTERNAL there;
the CLI remains a frozen compatibility surface.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import contracts, persistence
from .contracts import ContractError


@dataclass(frozen=True)
class Result:
    exit_code: int
    message: str
    artifacts: tuple[str, ...] = field(default_factory=tuple)
    state_changed: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def format_result(result: Result) -> str:
    """The operator-visible text, byte-identical to the pre-API CLI output."""
    return result.message


_RUNTIME = None

DEFAULTS = dict(
    run_root=None, project=None, stage=None, retry=False, provider=None, model=None,
    effort=None, workload=None, transport_provider=None, availability="unknown",
    quota="unknown", fallback=None, references_file=None, references_text=None,
    restart_context=None, motion=None, assets=None, target=None, lenses=None,
    synthetic_validation=False, reasoner=None, reason=None, summary=None,
    evidence=None, json=False, adopt_existing=False, request=None, request_file=None,
    run_id=None, status=None, file=None, input=None, outcome=None, timeout=120,
    gate=None, identity=None, note=None, migrate=False, reviewer_identity=None,
    kind=None, role=None, escalate=False, reviewer_role=None, worker_role=None,
    execution=None, apply=None, limit=50, family=None, adapter=None, subject=None,
    dependency=None, inspect=False, task_id=None, provider_source=None,
    provider_name=None, provider_model=None, provider_request_id=None,
    provider_run_id=None, evidence_policy=None,
)
"""Every option any wrapped command reads, so the API can call them directly."""


def bind(runtime) -> None:
    """Bind this module to a loaded ``scripts/ariadne.py``.

    ``runtime`` may be the module itself or a zero-argument resolver, so a
    loader that execs the runtime without registering it in ``sys.modules``
    cannot break the binding at import time.
    """
    global _RUNTIME
    _RUNTIME = runtime


def runtime():
    value = _RUNTIME() if callable(_RUNTIME) else _RUNTIME
    if value is None:
        raise ContractError(
            "the orchestration API is not bound to a runtime; import scripts/ariadne.py first"
        )
    return value


def _digest(path: Path | None) -> str | None:
    if path is None:
        return None
    target = persistence.state_path(Path(path))
    return hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None


def _namespace(options: dict) -> argparse.Namespace:
    values = dict(DEFAULTS)
    values.update({key: value for key, value in options.items() if value is not None})
    return argparse.Namespace(**values)


def _call(
    function_name: str,
    options: dict | None = None,
    args: argparse.Namespace | None = None,
) -> Result:
    """Invoke one runtime command in-process, capturing its operator text.

    Refusals follow the CLI contract exactly: a raised runtime error becomes a
    ``Result`` with exit code 1 and the same ``STOPPED:`` text the command line
    prints, so the programmatic and command-line surfaces cannot disagree.
    """
    namespace = args if args is not None else _namespace(options or {})
    run_root = getattr(namespace, "run_root", None)
    before = _digest(run_root)
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            code = getattr(runtime(), function_name)(namespace)
    except RuntimeError as exc:
        text = buffer.getvalue()
        if text:
            sys.stdout.write(text)
        return Result(exit_code=1, message=f"STOPPED: {exc}\n",
                      state_changed=before != _digest(run_root))
    except BaseException:
        text = buffer.getvalue()
        if text:
            sys.stdout.write(text)
        raise
    return Result(
        exit_code=int(code or 0),
        message=buffer.getvalue(),
        artifacts=tuple(str(item) for item in (getattr(namespace, "file", None) or ())),
        state_changed=before != _digest(run_root),
    )


# ------------------------------------------------------------- run lifecycle

def start_run(
    project=None,
    run_root=None,
    request=None,
    request_file=None,
    reasoner=None,
    adopt_existing=False,
    run_id=None,
    *,
    args: argparse.Namespace | None = None,
) -> Result:
    return _call("start", {
        "project": project, "run_root": run_root, "request": request,
        "request_file": request_file, "reasoner": reasoner,
        "adopt_existing": adopt_existing, "run_id": run_id,
    }, args)


def status(run_root=None, project=None, as_json=False, *, args=None) -> Result:
    return _call("status", {"run_root": run_root, "project": project, "json": as_json}, args)


def approve_gate(
    gate=None,
    run_root=None,
    project=None,
    identity=None,
    note=None,
    *,
    args: argparse.Namespace | None = None,
) -> Result:
    return _call("approve_gate", {
        "gate": gate, "run_root": run_root, "project": project,
        "identity": identity, "note": note,
    }, args)


def prepare_next(run_root=None, project=None, *, args=None, **options) -> Result:
    return _call("prepare_next", {"run_root": run_root, "project": project, **options}, args)


def record_result(run_root=None, project=None, *, args=None, **options) -> Result:
    return _call("structural_result", {"run_root": run_root, "project": project, **options}, args)


def ingest_return(run_root=None, project=None, input=None, *, args=None) -> Result:
    return _call("ingest_return", {"run_root": run_root, "project": project, "input": input}, args)


def validate_worker(run_root=None, project=None, timeout=120, *, args=None) -> Result:
    return _call("validate_worker", {"run_root": run_root, "project": project, "timeout": timeout}, args)


def prepare_review(run_root=None, project=None, target=None, lenses=None, *, args=None) -> Result:
    return _call("prepare_next", {
        "run_root": run_root, "project": project, "target": target, "lenses": lenses,
    }, args)


def ingest_review(
    run_root=None,
    project=None,
    input=None,
    reviewer_identity=None,
    kind=None,
    *,
    args=None,
) -> Result:
    return _call("ingest_review", {
        "run_root": run_root, "project": project, "input": input,
        "reviewer_identity": reviewer_identity, "kind": kind,
    }, args)


def record_acceptance(run_root=None, project=None, outcome=None, *, args=None) -> Result:
    return _call("record_acceptance", {
        "run_root": run_root, "project": project, "outcome": outcome,
    }, args)


def recovery_report(run_root=None, project=None, *, args=None) -> Result:
    """Inspect interrupted work. Read-only: it never infers that an operation succeeded."""
    namespace = args if args is not None else _namespace({"run_root": run_root, "project": project})
    root = runtime().resolve_run_root(namespace)
    report = persistence.recovery_report(Path(root))
    return Result(
        exit_code=0 if report["status"] == "clean" else 2,
        message=json.dumps(report, indent=2, sort_keys=True) + "\n",
        state_changed=False,
    )


# ------------------------------------------------- AR-202 adaptive operations

def execution_status(run_root=None, project=None, as_json=False, *, args=None) -> Result:
    """Show engine-created executions, the latest characterisation/route/context, and failures."""
    return _call("execution_status_command", {
        "run_root": run_root, "project": project, "json": as_json,
    }, args)


def engine_events(run_root=None, project=None, limit=50, as_json=False, *, args=None) -> Result:
    """Print the canonical append-only engine event log with its integrity check."""
    return _call("engine_events_command", {
        "run_root": run_root, "project": project, "limit": limit, "json": as_json,
    }, args)


def propose_recovery(run_root=None, project=None, target=None, *, args=None) -> Result:
    """Inspect divergences and the safe action (or explicit refusal) for each. Read-only."""
    return _call("recover_command", {
        "run_root": run_root, "project": project, "target": target,
    }, args)


def apply_recovery(
    run_root=None,
    project=None,
    action=None,
    target=None,
    identity=None,
    reason=None,
    *,
    args=None,
) -> Result:
    """Apply one safe recovery action through the engine's authoritative boundary."""
    return _call("recover_command", {
        "run_root": run_root, "project": project, "apply": action, "target": target,
        "identity": identity, "reason": reason,
    }, args)


def characterize_task(state, *, project, stage, task_id="", transport=None, request=None, dependencies=()) -> dict:
    """Deterministic task characterisation (same function the runtime executes)."""
    from . import routing

    return routing.characterize(
        state, project=Path(project), stage=stage, task_id=task_id, transport=transport,
        request=request, dependencies=tuple(dependencies or ()),
    )


def decide_context(state, *, stage, candidates, characterisation=None, run_root=None, revision_hash="") -> dict:
    """One context decision over the candidate sources the transport declared."""
    from . import context

    return context.decide(
        state, stage=stage, candidates=candidates, characterisation=characterisation,
        run_root=Path(run_root) if run_root else None, revision_hash=revision_hash,
    )


def select_route(state, *, stage, characterisation, **options) -> dict:
    """One routing decision under the declared ordered rules."""
    from . import routing

    return routing.route(state, stage=stage, characterisation=characterisation, **options)


def create_execution(state, *, task_id, role, adapter, **options) -> dict:
    """Create an engine-owned execution identity (the id is always generated here)."""
    from . import execution

    return execution.create(state, task_id=task_id, role=role, adapter=adapter, **options)


def observe_execution(state, execution_id, *, provider="", model="", source="", evidence=()) -> dict:
    """Record runtime-observed identity. Worker claims are refused by design."""
    from . import execution

    return execution.observe(
        state, execution_id, provider=provider, model=model, source=source, evidence=tuple(evidence),
    )


def record_failure(state, *, source, operation, evidence, **options) -> dict:
    """Classify and record one failure (unknown input stays UNKNOWN)."""
    from . import execution

    return execution.record_failure(
        state, source=source, operation=operation, evidence=tuple(evidence), **options,
    )


def execution_report(state) -> dict:
    """The execution/failure summary the operator command prints."""
    from . import execution

    return execution.status_report(state)


# ------------------------------------------------ AR-202D design intelligence

def characterize_design_task(
    state,
    *,
    project,
    stage,
    request="",
    task_id="",
    transport=None,
    characterisation=None,
    reference_adapters=None,
    capture_adapters=None,
    declared=None,
) -> dict:
    """Design task characterisation (same function the runtime executes)."""
    from . import design

    return design.characterize(
        state, project=Path(project), stage=stage, request=request, task_id=task_id,
        transport=transport, characterisation=characterisation,
        reference_adapters=reference_adapters, capture_adapters=capture_adapters, declared=declared,
    )


def design_plan(state, characterisation, *, task_id="") -> dict:
    """Select and record the design pipeline for one characterisation."""
    from . import design

    return design.plan(state, characterisation, task_id=task_id)


def discover_references(state, adapters, *, query="", task_id="", source_type="") -> dict:
    """Run discovery through the declared adapters and record every candidate as FOUND."""
    from . import references as references_module

    candidate_rows = []
    for adapter_id, adapter in dict(adapters or {}).items():
        if not adapter.enabled() or "discover" not in adapter.capabilities():
            continue
        for candidate in adapter.discover({"query": query}):
            if not candidate.source or not candidate.locator:
                continue
            candidate_rows.append({
                "adapter": adapter_id,
                "source": candidate.source,
                "locator": candidate.locator,
                "title": candidate.title or candidate.source,
                "source_type": candidate.source_type,
            })
    typed = [row for row in candidate_rows if not source_type or row["source_type"] == source_type]
    return {"candidates": typed, "adapters": sorted(dict(adapters or {}).keys())}


def register_reference(state, **options) -> dict:
    """Record one FOUND reference (the provenance lifecycle starts here)."""
    from . import references as references_module

    return references_module.register(state, **options)


def inspect_reference(state, reference_id, **options) -> dict:
    from . import references as references_module

    return references_module.inspect(state, reference_id, **options)


def analyse_reference(state, reference_id, **options) -> dict:
    from . import references as references_module

    return references_module.analyse(state, reference_id, **options)


def mark_reference_used(state, reference_id, **options) -> dict:
    from . import references as references_module

    return references_module.mark_used(state, reference_id, **options)


def evaluate_component(state, **options) -> dict:
    """Evaluate one component candidate against the minimum-solution ladder."""
    from . import components

    return components.evaluate(state, **options)


def create_design_direction(state, **options) -> dict:
    from . import design

    return design.create_direction(state, **options)


def approve_design_direction(state, direction_id, **options) -> dict:
    """Record the human G1D approval of one design-direction record."""
    from . import design

    return design.approve_direction(state, direction_id, **options)


def record_rendered_evidence(state, **options) -> dict:
    from . import render

    return render.record(state, **options)


def prepare_design_review(state, **options) -> dict:
    from . import critique

    return critique.prepare_review(state, **options)


def ingest_design_review(state, **options) -> dict:
    from . import critique

    return critique.build_review(state, **options)


def propose_refinement(state, finding_id, **options) -> dict:
    from . import critique

    return critique.propose_refinement(state, finding_id, **options)


def record_refinement(state, refinement_id, **options) -> dict:
    from . import critique

    return critique.record_refinement(state, refinement_id, **options)


def design_report(state) -> dict:
    """The design-intelligence summary the operator command prints."""
    from . import design

    return design.report(state)


def route_design_evidence(state, **options) -> dict:
    """Route design-evidence needs to declared adapters through AR-202 routing."""
    from . import routing

    return routing.route_evidence(state, **options)


# ------------------------------------------------ AR-203 verification plane

def inspect_capabilities(
    run_root=None,
    project=None,
    family=None,
    adapter=None,
    as_json=False,
    *,
    args: argparse.Namespace | None = None,
) -> Result:
    """Inspect the capability registry (declared, observed, exercised, verified)."""
    return _call("capabilities_command", {
        "run_root": run_root, "project": project, "family": family,
        "adapter": adapter, "json": as_json,
    }, args)


def record_capability_observation(
    run_root=None,
    project=None,
    input=None,
    *,
    args: argparse.Namespace | None = None,
) -> Result:
    """Declare capabilities and run deterministic probes through the same engine path as the CLI."""
    return _call("capabilities_command", {
        "run_root": run_root, "project": project, "input": input,
    }, args)


def verify_claim(run_root=None, project=None, input=None, *, args=None) -> Result:
    """Record one verification claim (level obligations are enforced by the engine)."""
    return _call("verify_command", {
        "run_root": run_root, "project": project, "input": input,
    }, args)


def verification_status(run_root=None, project=None, subject=None, dependencies=None, as_json=False, *, args=None) -> Result:
    """Inspect verification status; stale records never answer as current."""
    return _call("verify_command", {
        "run_root": run_root, "project": project, "status": True, "subject": subject,
        "dependency": list(dependencies or []), "json": as_json,
    }, args)


def create_decision_batch(run_root=None, project=None, input=None, *, args=None) -> Result:
    """Evaluate one bounded decision batch through the engine boundary."""
    return _call("decide_command", {
        "run_root": run_root, "project": project, "input": input,
    }, args)


def record_decision(run_root=None, project=None, input=None, *, args=None) -> Result:
    """Record the action an accepted decision drove (the decision -> action edge)."""
    return _call("decide_command", {
        "run_root": run_root, "project": project, "input": input,
    }, args)


def inspect_decision(run_root=None, project=None, task_id=None, as_json=False, *, args=None) -> Result:
    """Inspect the decision trace: what judgement was produced and what it drove."""
    return _call("decide_command", {
        "run_root": run_root, "project": project, "inspect": True,
        "task_id": task_id, "json": as_json,
    }, args)


def inspect_execution_identity(run_root=None, project=None, execution=None, task_id=None, as_json=False, *, args=None) -> Result:
    """Inspect engine-bound execution provenance and identity claim levels."""
    return _call("provenance_command", {
        "run_root": run_root, "project": project, "execution": execution,
        "task_id": task_id, "json": as_json,
    }, args)


def execution_provenance(state, execution_id) -> dict:
    """The full provenance view for one engine-created execution."""
    from . import provenance

    return provenance.execution_provenance(state, execution_id)


def record_provider_observation(state, execution_id, **options) -> dict:
    """Record a provider-reported identity for one execution (never worker prose)."""
    from . import provenance

    return provenance.record_provider_observation(state, execution_id, **options)


def record_execution_usage(state, execution_id, **options) -> dict:
    """Record measured provider usage for one execution. Unknown fields stay unknown."""
    from . import execution as execution_module

    return execution_module.record_usage(state, execution_id, **options)


def classify_failure_with_decision(state, **options) -> dict:
    """Deterministic failure classification first; bounded judgement only when unmapped."""
    from . import execution as execution_module

    return execution_module.classify_with_decision(state, **options)


def record_verification(state, **options) -> dict:
    """Create one verification record (engine-level; the CLI uses the same function)."""
    from . import verification

    return verification.create(state, **options)


def verification_report(state, *, subject="", current=None) -> dict:
    """Verification status and counters for one run state."""
    from . import verification

    return {
        "status": verification.status(state, subject=subject, current=current),
        "summary": verification.summarise(state),
    }


def declare_capability(state, **options) -> dict:
    """Record one capability declaration (never more than DECLARED)."""
    from . import capabilities

    return capabilities.declare(state, **options)


def observe_capability(state, **options) -> dict:
    """Record one observed capability fact with its evidence."""
    from . import capabilities

    return capabilities.observe(state, **options)


def run_capability_probe(state, probe) -> dict:
    """Run one deterministic capability probe and record its observation."""
    from . import capabilities

    return capabilities.run_probe(state, probe)


def capability_report(state, *, family="", adapter="") -> dict:
    """The capability registry view and counters for one run state."""
    from . import capabilities

    rows = [
        dict(row) for row in capabilities.records(state)
        if (not family or str(row.get("family", "")) == family)
        and (not adapter or str(row.get("adapter", "")) == adapter)
    ]
    return {"summary": capabilities.summarise(state), "records": rows}


def evaluate_decisions(state, **options) -> dict:
    """Evaluate one bounded decision batch (engine-level)."""
    from . import decisions

    return decisions.batch.evaluate(state, **options)


def decision_report(state, *, task_id="") -> dict:
    """The decision trace and counters for one run state."""
    from . import decisions

    return {
        "summary": decisions.batch.summarise(state),
        "trace": decisions.batch.trace(state, task_id=task_id),
    }


# ------------------------------------------------- AR-205D decision intelligence


def compile_decisions(state, **options) -> dict:
    """Compile a decision plan: classify each requirement before asking anyone."""
    from . import decisions

    return decisions.compiler.compile_plan(state, **options)


def compile_decision_graph(state, **options) -> dict:
    """Build the decision graph for a compiled plan (validated, acyclic)."""
    from . import decisions

    plan = options.pop("plan", None)
    plan_id = str(options.pop("plan_id", "") or "")
    if plan is None:
        plan = decisions.compiler.plan(state, plan_id) if plan_id else decisions.compiler.latest(
            state, task_id=str(options.get("task_id", "") or ""),
        )
    if plan is None:
        raise contracts.ContractError("no compiled decision plan matches; compile one first")
    return decisions.graph.from_plan(state, plan, **options)


def decision_advice(state, *, family="", **options) -> dict:
    """Ask one real engine integration for bounded advice (never authorization)."""
    from . import decisions

    advice = {
        "failure-classification": decisions.integrations.classify_failure,
        "review-escalation": decisions.integrations.review_escalation,
        "evidence-relevance": decisions.integrations.evidence_relevance,
        "route-family": decisions.integrations.route_family,
    }
    handler = advice.get(str(family))
    if handler is None:
        raise contracts.ContractError(
            "unknown decision advice family: " + str(family) + "; declared: " + ", ".join(sorted(advice))
        )
    return handler(state, **options)


def decision_trace(state, *, task_id="") -> dict:
    """The record-derived decision trace and its structured explanation."""
    from . import decisions

    return decisions.trace.explain(state, task_id=task_id)


def decision_intelligence_report(state, *, task_id="") -> dict:
    """Structural decision-intelligence economics for one run state."""
    from . import decisions

    return {
        "summary": decisions.economics.summarise(state),
        "intelligence": decisions.economics.intelligence_economics(state, task_id=task_id),
    }


def justify_generation(state, **options) -> dict:
    """Record why generative execution is justified (provenance, not permission)."""
    from . import decisions

    return decisions.generation.justify(state, **options)


def record_decision_outcome(state, **options) -> dict:
    """Record raw outcome evidence for one decision (no self-tuning)."""
    from . import decisions

    return decisions.calibration.record_outcome(state, **options)


def invalidate_decision_cache(state, **options) -> dict:
    """Revoke or supersede cached decisions with a recorded reason."""
    from . import decisions

    touched = decisions.cache.invalidate(state, **options)
    return {"invalidated": touched, "count": len(touched)}


# ------------------------------------------------------ AR-204 harness economics


def record_execution_billing(state, execution_id, **options) -> dict:
    """Record a provider-reported billing amount for one execution (measured only)."""
    from . import economics

    return economics.record_billing(state, execution_id, **options)


def record_execution_cache(state, execution_id, **options) -> dict:
    """Record what was measured about caching, keeping structural data separate."""
    from . import economics

    return economics.record_cache_observation(state, execution_id, **options)


def task_economics(state, task_id, *, profile_id="", current=None) -> dict:
    """The task tree, its cost shares and its verified completion cost."""
    from . import economics

    tree = economics.task_tree(state, task_id)
    return {
        "tree": tree,
        "costs": economics.task_tree_costs(tree),
        "cost": economics.task_cost(state, task_id, profile_id=profile_id, current=current),
        "verified_completion": economics.verified_completion_cost(
            state, task_id, profile_id=profile_id, current=current
        ),
    }


def economics_report(state, *, profile_id="") -> dict:
    """Run-level economics: context attribution, decision cost and totals."""
    from . import economics

    return {
        "summary": economics.summarise(state),
        "context": economics.context_economics(state),
        "decisions": economics.decision_economics(state),
        "efficiency": _efficiency_view(state),
    }


def efficiency_report(state) -> dict:
    """The run's efficiency configuration and what it would change."""
    return _efficiency_view(state)


def _efficiency_view(state) -> dict:
    from . import efficiency, tooling

    return {
        "config": efficiency.efficiency_config(state),
        "description": efficiency.describe(state),
        "behaviour_sensitive": list(efficiency.BEHAVIOUR_SENSITIVE),
        "safe_defaults": list(efficiency.SAFE_DEFAULTS),
        "capability_packs": {
            "core": list(tooling.CORE_CAPABILITIES),
            "packs": sorted(tooling.CAPABILITY_PACKS),
        },
    }


def inspect_request(state=None, *, packet=None, text="", provider="", model="", profile="legacy") -> dict:
    """Render the request structure a packet would produce (offline, read-only).

    The render is redacted and is never used to build a request.
    """
    from . import harness, prompting

    if packet is not None and not text:
        text = Path(packet).read_text(encoding="utf-8")
    if not str(text):
        return {"render": {}, "problems": ["no packet or text was supplied to render"]}
    compacted = prompting.compact_packet_text(str(text), profile=profile)
    mapping = harness.packet_map(compacted["text"], provider=provider, model=model)
    return {
        "prompt_profile": compacted["profile"],
        "profile_applied": compacted["applied"],
        "profile_removed_bytes": compacted["removed_bytes"],
        "harness_map": mapping,
        "render": harness.packet_render(compacted["text"], provider=provider, model=model),
        "problems": [],
    }


def inspect_tool_packs(*, root=None, stage="", selected_skills=(), required_capabilities=()) -> dict:
    """The measured tool-schema surface and the deterministic pack selection."""
    from . import tooling

    return {
        "sizes": tooling.pack_sizes(root=Path(root) if root else None),
        "selection": tooling.select_packs(
            stage=stage,
            selected_skills=selected_skills,
            required_capabilities=required_capabilities,
        ),
        "discovery": tooling.discover(root=Path(root) if root else None),
    }


def externalize_output(state, *, data, tool, command="", execution_id="", root=None, force=False) -> dict:
    """Store one large tool output as a durable artifact and return its reference."""
    from . import artifacts

    run_root = Path(root) if root else Path(str(state.get("run_root", ".")))
    record = artifacts.externalize(
        run_root,
        data=data,
        tool=tool,
        command=command,
        source_execution=execution_id,
        task_id=_task_of(state, execution_id),
        run_id=str(state.get("run_id", "")),
        force=force,
    )
    if record["status"] != artifacts.STATUS_INLINE:
        contracts.require_collection_capacity(state, "artifacts")
        state.setdefault("artifacts", []).append(record)
    return record


def retrieve_artifact(state, artifact_id) -> dict:
    """Return the full artifact for a recorded reference (digest re-checked)."""
    from . import artifacts

    for record in state.get("artifacts") or []:
        if isinstance(record, dict) and str(record.get("artifact_id", "")) == str(artifact_id):
            return artifacts.retrieve(record)
    return {"ok": False, "problems": [f"no artifact record matches {artifact_id!r}"], "text": ""}


def _task_of(state, execution_id) -> str:
    from . import execution

    record = execution.execution(state, str(execution_id)) if execution_id else None
    return str((record or {}).get("task_id", ""))


def compact_history(state, entries, *, policy="structured_v1", reason="", root=None) -> dict:
    """Archive the full history and return a structured active view."""
    from . import history

    run_root = Path(root) if root else Path(str(state.get("run_root", ".")))
    result = history.compact(run_root, entries, policy=policy, reason=reason)
    contracts.require_collection_capacity(state, "compaction_records")
    state.setdefault("compaction_records", []).append(result)
    return result


def plan_execution_path(*, stakes="UNKNOWN", **options) -> dict:
    """The policy-derived execution path for one task (simple / standard / complex)."""
    from . import orchestration

    return orchestration.path_plan(stakes=stakes, **options)


def orchestration_report(state, task_id) -> dict:
    """What orchestration bought for one task, from measured records only."""
    from . import orchestration

    return orchestration.orchestration_economics(state, task_id)


def audit_prompts(*, root=None, paths=()) -> dict:
    """The static prompt audit (offline, read-only)."""
    from . import prompting

    if not paths:
        return {"problems": ["no prompt paths were supplied to audit"]}
    directory = Path(root) if root else Path(".")
    return prompting.audit_prompt_directory(directory, paths)


def set_efficiency(state, **flags) -> dict:
    """Record the run's efficiency configuration (behaviour-sensitive flags)."""
    from . import efficiency

    return efficiency.set_efficiency_config(state, **flags)


# ------------------------------------------------------ AR-205 release migration

def _migration_run_root(run_root=None, project=None, args: argparse.Namespace | None = None) -> Path:
    namespace = args if args is not None else _namespace({"run_root": run_root, "project": project})
    return Path(runtime().resolve_run_root(namespace))


def _migration_action(action, run_root=None, project=None, *, args=None) -> Result:
    from . import migration

    try:
        root = _migration_run_root(run_root, project, args)
        if action == "plan":
            value = migration.plan(root)
        elif action == "apply":
            value = migration.apply(root)
        elif action == "rollback":
            value = migration.rollback(root)
        else:
            value = migration.report_view(root)
    except ContractError as exc:
        return Result(exit_code=1, message=f"STOPPED: {exc}\n")
    if action == "report":
        return Result(exit_code=0, message=json.dumps(value, indent=2, sort_keys=True) + "\n")
    return Result(exit_code=0, message=migration.render(value))


def plan_migration(run_root=None, project=None, *, args: argparse.Namespace | None = None) -> Result:
    """Dry run: what a v1 -> v2 migration would change, preserve, back up and refuse."""
    return _migration_action("plan", run_root, project, args=args)


def apply_migration(run_root=None, project=None, *, args: argparse.Namespace | None = None) -> Result:
    """Apply the additive record-contract migration after verifying the plan."""
    return _migration_action("apply", run_root, project, args=args)


def rollback_migration(run_root=None, project=None, *, args: argparse.Namespace | None = None) -> Result:
    """Restore the preserved pre-migration bytes while that remains honest."""
    return _migration_action("rollback", run_root, project, args=args)


def migration_report(run_root=None, project=None, *, args: argparse.Namespace | None = None) -> Result:
    """The durable migration evidence records for one run."""
    return _migration_action("report", run_root, project, args=args)


__all__ = [
    "Result",
    "format_result",
    "bind",
    "runtime",
    "start_run",
    "status",
    "approve_gate",
    "prepare_next",
    "record_result",
    "ingest_return",
    "validate_worker",
    "prepare_review",
    "ingest_review",
    "record_acceptance",
    "recovery_report",
    "execution_status",
    "engine_events",
    "propose_recovery",
    "apply_recovery",
    "characterize_task",
    "decide_context",
    "select_route",
    "create_execution",
    "observe_execution",
    "record_failure",
    "execution_report",
    "characterize_design_task",
    "design_plan",
    "discover_references",
    "register_reference",
    "inspect_reference",
    "analyse_reference",
    "mark_reference_used",
    "evaluate_component",
    "create_design_direction",
    "approve_design_direction",
    "record_rendered_evidence",
    "prepare_design_review",
    "ingest_design_review",
    "propose_refinement",
    "record_refinement",
    "design_report",
    "route_design_evidence",
    "inspect_capabilities",
    "record_capability_observation",
    "verify_claim",
    "verification_status",
    "create_decision_batch",
    "record_decision",
    "inspect_decision",
    "inspect_execution_identity",
    "execution_provenance",
    "record_provider_observation",
    "record_execution_usage",
    "classify_failure_with_decision",
    "record_verification",
    "verification_report",
    "declare_capability",
    "observe_capability",
    "run_capability_probe",
    "capability_report",
    "evaluate_decisions",
    "decision_report",
    "compile_decisions",
    "compile_decision_graph",
    "decision_advice",
    "decision_trace",
    "decision_intelligence_report",
    "justify_generation",
    "record_decision_outcome",
    "invalidate_decision_cache",
    "record_execution_billing",
    "record_execution_cache",
    "task_economics",
    "economics_report",
    "efficiency_report",
    "inspect_request",
    "inspect_tool_packs",
    "externalize_output",
    "retrieve_artifact",
    "compact_history",
    "plan_execution_path",
    "orchestration_report",
    "audit_prompts",
    "set_efficiency",
    "plan_migration",
    "apply_migration",
    "rollback_migration",
    "migration_report",
]
