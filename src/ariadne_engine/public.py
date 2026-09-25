"""The deliberate Ariadne v2 public Python surface.

``ariadne_engine`` contains far more than a consumer should depend on. This
module names the small, coherent set of operations Ariadne v2 supports as a
product surface, classifies each one, and provides the one supported way to
embed the engine without the command line.

Stability classes:

``STABLE_V2``
    Covered by release tests, exercised through both the CLI and this module,
    and safe for a consumer such as an editor integration to bind to. Breaking
    a name here requires a major version.
``PROVISIONAL``
    Real and tested, but expected to evolve within v2. Consumers may use it
    with that expectation.
``INTERNAL``
    Exported for the documented loading path or for the runtime itself. Not a
    product surface; it may change in any release.

Names that appear in neither list are internal and must not be imported by a
consumer. The release tests assert that every name exported by
:mod:`ariadne_engine.api` carries exactly one classification, so an addition
cannot become public by accident.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from . import api, contracts, migration, package_version
from .contracts import ContractError

STABLE_V2 = (
    "Result",
    "format_result",
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
    "propose_recovery",
    "apply_recovery",
    "engine_events",
    "execution_status",
    "inspect_capabilities",
    "verify_claim",
    "verification_status",
    "inspect_execution_identity",
    "create_decision_batch",
    "record_decision",
    "inspect_decision",
    "task_economics",
    "economics_report",
    "efficiency_report",
    "record_execution_billing",
    "record_execution_cache",
    "plan_migration",
    "apply_migration",
    "rollback_migration",
    "migration_report",
    "connect",
    "EngineClient",
    "describe_public_api",
    "PUBLIC_SURFACE",
)

PROVISIONAL = (
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
    "record_capability_observation",
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
    "inspect_request",
    "inspect_tool_packs",
    "externalize_output",
    "retrieve_artifact",
    "compact_history",
    "plan_execution_path",
    "orchestration_report",
    "audit_prompts",
    "set_efficiency",
)

INTERNAL = (
    "bind",
    "runtime",
)

PUBLIC_SURFACE = {
    name: "STABLE_V2" for name in STABLE_V2
} | {
    name: "PROVISIONAL" for name in PROVISIONAL
} | {
    name: "INTERNAL" for name in INTERNAL
}
"""Name -> stability class for every exported api operation."""


def describe_public_api() -> dict:
    """The machine-readable stability table (no imports beyond this package)."""
    return {
        "engine_version": package_version(),
        "engine_contract": contracts.ENGINE_CONTRACT,
        "stable_v2": sorted(STABLE_V2),
        "provisional": sorted(PROVISIONAL),
        "internal": sorted(INTERNAL),
        "note": "names not listed here are internal and are not a product surface",
    }


def _runtime_path(runtime_root: Path) -> Path:
    root = Path(runtime_root)
    if root.is_file():
        return root
    candidate = root / "scripts" / "ariadne.py"
    if not candidate.is_file():
        raise ContractError(
            f"No Ariadne runtime at {runtime_root}; expected scripts/ariadne.py beneath it"
        )
    return candidate


def _load_runtime(runtime_root: Path):
    path = _runtime_path(runtime_root)
    spec = importlib.util.spec_from_file_location("ariadne_runtime", path)
    if spec is None or spec.loader is None:
        raise ContractError(f"The Ariadne runtime could not be loaded: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tree_version(tree: Path) -> str:
    path = Path(tree) / "VERSION"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def _verify_versions(runtime) -> None:
    runtime_tree = Path(str(getattr(runtime, "__file__", ""))).resolve().parent.parent
    engine_tree = Path(__file__).resolve().parent.parent
    runtime_version = _tree_version(runtime_tree)
    engine_version = _tree_version(engine_tree)
    if runtime_version and engine_version and runtime_version != engine_version:
        raise ContractError(
            f"The runtime at {runtime_tree} is version {runtime_version} but the engine in use is "
            f"{engine_version}; refusing to mix two Ariadne versions"
        )


class EngineClient:
    """One bound engine runtime, callable without the command line.

    Every method returns the same :class:`ariadne_engine.api.Result` the CLI
    produces, so a consumer cannot obtain weaker enforcement than an operator.
    The client never writes state by itself; it only asks the engine to.
    """

    def __init__(self, runtime, *, runtime_root: Path | None = None) -> None:
        self.runtime = runtime
        self.runtime_root = Path(runtime_root) if runtime_root else None

    @property
    def version(self) -> str:
        return package_version()

    def describe(self) -> dict:
        return {
            "engine_version": self.version,
            "engine_contract": contracts.ENGINE_CONTRACT,
            "run_schema": contracts.SCHEMA_RUN,
            "record_schema": contracts.SCHEMA_RECORD,
            "public_api": describe_public_api(),
        }

    def start_run(self, **options) -> api.Result:
        return api.start_run(**options)

    def status(self, **options) -> api.Result:
        return api.status(**options)

    def prepare_next(self, **options) -> api.Result:
        return api.prepare_next(**options)

    def record_result(self, **options) -> api.Result:
        return api.record_result(**options)

    def ingest_return(self, **options) -> api.Result:
        return api.ingest_return(**options)

    def validate_worker(self, **options) -> api.Result:
        return api.validate_worker(**options)

    def prepare_review(self, **options) -> api.Result:
        return api.prepare_review(**options)

    def ingest_review(self, **options) -> api.Result:
        return api.ingest_review(**options)

    def record_acceptance(self, **options) -> api.Result:
        return api.record_acceptance(**options)

    def approve_gate(self, **options) -> api.Result:
        return api.approve_gate(**options)

    def recovery_report(self, **options) -> api.Result:
        return api.recovery_report(**options)

    def propose_recovery(self, **options) -> api.Result:
        return api.propose_recovery(**options)

    def apply_recovery(self, **options) -> api.Result:
        return api.apply_recovery(**options)

    def engine_events(self, **options) -> api.Result:
        return api.engine_events(**options)

    def inspect_capabilities(self, **options) -> api.Result:
        return api.inspect_capabilities(**options)

    def verify_claim(self, **options) -> api.Result:
        return api.verify_claim(**options)

    def verification_status(self, **options) -> api.Result:
        return api.verification_status(**options)

    def inspect_execution_identity(self, **options) -> api.Result:
        return api.inspect_execution_identity(**options)

    def create_decision_batch(self, **options) -> api.Result:
        return api.create_decision_batch(**options)

    def inspect_decision(self, **options) -> api.Result:
        return api.inspect_decision(**options)

    def task_economics(self, **options) -> api.Result:
        return api.task_economics(**options)

    def economics_report(self, **options) -> api.Result:
        return api.economics_report(**options)

    def plan_migration(self, **options) -> api.Result:
        return api.plan_migration(**options)

    def apply_migration(self, **options) -> api.Result:
        return api.apply_migration(**options)

    def rollback_migration(self, **options) -> api.Result:
        return api.rollback_migration(**options)

    def migration_report(self, **options) -> api.Result:
        return api.migration_report(**options)


def connect(runtime_root=None) -> EngineClient:
    """Bind the engine to a runtime tree and return a client.

    ``runtime_root`` is a checkout or installed runtime directory (or the
    ``scripts/ariadne.py`` path itself). Without it, an already-loaded runtime
    is reused. No optional provider, editor, network or project dependency is
    imported by this call.
    """
    if runtime_root is None:
        runtime = api.runtime()
        root = Path(str(getattr(runtime, "__file__", ""))).resolve().parent.parent
        _verify_versions(runtime)
        return EngineClient(runtime, runtime_root=root)
    root = Path(runtime_root)
    runtime = _load_runtime(root)
    _verify_versions(runtime)
    api.bind(runtime)
    return EngineClient(runtime, runtime_root=root)


__all__ = [
    "STABLE_V2",
    "PROVISIONAL",
    "INTERNAL",
    "PUBLIC_SURFACE",
    "describe_public_api",
    "EngineClient",
    "connect",
]
