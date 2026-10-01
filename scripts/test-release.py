#!/usr/bin/env python3
"""AR-205 release tests: versions, public API, integration contract, migration.

Deterministic and offline. No model calls, no network, no writes outside a
temporary validation workspace. Run: python scripts/test-release.py
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ariadne_engine import (  # noqa: E402
    api,
    contracts,
    efficiency,
    integration,
    migration,
    persistence,
    public,
    release,
)


def load_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_script(name: str, filename: str):
    return load_path(name, ROOT / "scripts" / filename)


@contextlib.contextmanager
def workspace():
    path = ROOT / "validation" / f"release-self-test-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        if path.exists():
            last_error = None
            for attempt in range(5):
                try:
                    shutil.rmtree(path)
                    last_error = None
                    break
                except OSError as exc:
                    last_error = exc
                    time.sleep(0.05 * (attempt + 1))
            if last_error is not None:
                raise last_error


def run_runtime(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ariadne.py"), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or ROOT),
    )


def make_legacy_run(sandbox: Path, *, approve: bool = False, name: str = "legacy-project") -> tuple[Path, Path]:
    """A v1-era run: file schema 1, no engine marker, packet on disk, project ledger."""
    project = sandbox / name
    run_root = sandbox / f"{name}-ariadne"
    packet = run_root / "legacy-S1"
    packet.mkdir(parents=True)
    (packet / "manifest.json").write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    state = {
        "schema_version": 1,
        "run_id": "legacy",
        "project": str(project),
        "packets": [{"id": "legacy-S1", "stage": "S1", "path": str(packet)}],
        "next": "Complete the brief.",
    }
    if approve:
        state["approvals"] = [{
            "schema_version": 2,
            "approval_id": "legacy-approval",
            "gate": "G1",
            "identity": "previous-operator",
            "revision": "legacy-revision",
            "recorded_at": "2026-01-01T00:00:00Z",
        }]
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "ariadne-run.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    (project / ".ariadne").mkdir(parents=True)
    (project / ".ariadne" / "creative-evidence.json").write_text(
        json.dumps({"schema_version": 1, "skills": []}), encoding="utf-8"
    )
    (project / "PROJECT.md").write_text("# PROJECT: legacy\n", encoding="utf-8")
    return project, run_root


def state_bytes(run_root: Path) -> bytes:
    return (run_root / "ariadne-run.json").read_bytes()


def state_digest(run_root: Path) -> str:
    return hashlib.sha256(state_bytes(run_root)).hexdigest()


def mutate(path: Path, replacement: str):
    """Context manager: write replacement, then restore byte-exact."""
    original = path.read_bytes()
    path.write_text(replacement, encoding="utf-8")

    class Restorer:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            path.write_bytes(original)
            return False

    return Restorer()


def self_test() -> int:
    cases: list[tuple[str, bool]] = []

    def case(name: str, passed: bool) -> None:
        cases.append((name, bool(passed)))

    canonical = release.version(ROOT)

    # ------------------------------------------------ versions and release facts
    case("VERSION parses as a supported release version", bool(release.VERSION_RE.fullmatch(canonical)))
    case("VERSION is the v2 release candidate", canonical.startswith("2."))
    case("repository version surfaces agree", release.version_problems(ROOT) == [])
    backend = load_script("ariadne_release_backend_test", "build-release.py")
    case("the release builder reads the same VERSION", backend.version() == canonical)
    with mutate(ROOT / "VERSION", "9.9.9\n"):
        case("a mutated VERSION is detected", release.version_problems(ROOT) != [])
    with mutate(ROOT / "RELEASE-NOTES.md", "# Ariadne 9.9.9\n\nbody\n"):
        case("a mutated release-notes heading is detected", release.version_problems(ROOT) != [])
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    with mutate(ROOT / "README.md", readme.replace(canonical, "9.9.9")):
        case("a mutated install URL is detected", release.version_problems(ROOT) != [])
    example_path = ROOT / ".agents" / "skills" / "ariadne" / "references" / "installation.example.json"
    with mutate(
        example_path,
        json.dumps({"schema_version": 1, "version": "9.9.9", "ariadne_root": "x", "install_home": "y"}),
    ):
        case("a mutated installation example is detected", release.version_problems(ROOT) != [])

    run = run_runtime("--version")
    case(
        "the runtime CLI reports the canonical version",
        run.returncode == 0 and f"Ariadne {canonical}" in run.stdout,
    )
    case(
        "the runtime prints its schema and engine contract",
        f"engine contract {contracts.ENGINE_CONTRACT}" in run.stdout,
    )

    # ------------------------------------------------------------- public surface
    case("every exported operation carries exactly one stability class", release.public_surface_problems() == [])
    case(
        "the stable surface contains the embedding entry point",
        public.PUBLIC_SURFACE.get("connect") == "STABLE_V2",
    )
    case(
        "the stable surface contains the migration operations",
        all(public.PUBLIC_SURFACE.get(name) == "STABLE_V2" for name in (
            "plan_migration", "apply_migration", "rollback_migration", "migration_report",
        )),
    )
    description = public.describe_public_api()
    case(
        "the public description is coherent",
        description["engine_contract"] == contracts.ENGINE_CONTRACT
        and description["stable_v2"] and description["provisional"],
    )
    forbidden = {
        name for name in sys.modules
        if name.split(".")[0] in {"boreal", "tauri", "react", "opencode", "anthropic", "openai", "requests", "httpx"}
    }
    case("importing the public API loads no optional provider or consumer module", not forbidden)
    client = public.connect(ROOT)
    case("connect() binds a runtime client", isinstance(client, public.EngineClient))
    case("the client reports the canonical engine version", client.version == canonical)
    missing_runtime = client.status(project=str(ROOT / "validation" / "does-not-exist"))
    case("a status call on a missing project refuses without crashing", missing_runtime.exit_code == 1)
    try:
        public.connect(ROOT / "validation" / "no-runtime-here")
        refused = False
    except contracts.ContractError:
        refused = True
    case("connect() refuses a directory that is not a runtime", refused)

    # --------------------------------------------------------- integration contract
    negotiated, problems = integration.negotiate(integration.CONTRACT_FIXTURES["happy_path"])
    case("a compatible consumer negotiates cleanly", problems == [])
    case(
        "the contract advertises operations and its authority boundary",
        "approve" in negotiated["operations"] and "engine" in negotiated["authority"].lower(),
    )
    _, problems = integration.negotiate(integration.CONTRACT_FIXTURES["unsupported_version"])
    case("an unsupported protocol version is refused explicitly", any("outside the supported range" in p for p in problems))
    _, problems = integration.negotiate(integration.CONTRACT_FIXTURES["missing_capability"])
    case("a missing required capability is refused explicitly", any("teleportation" in p for p in problems))
    negotiated, problems = integration.negotiate(integration.CONTRACT_FIXTURES["unknown_fields"])
    case(
        "unknown request fields are reported and ignored",
        problems == [] and set(negotiated["ignored_fields"]) >= {"grant_approval", "trust_me"},
    )
    _, problems = integration.negotiate(integration.CONTRACT_FIXTURES["optional_capability_absent"])
    case("an absent optional capability is not an error", problems == [])
    with_old_protocol = dict(integration.CONTRACT_FIXTURES["happy_path"], protocol_version=0)
    _, problems = integration.negotiate(with_old_protocol)
    case("a below-range protocol version is refused", any("outside the supported range" in p for p in problems))

    with workspace() as sandbox:
        project = sandbox / "fresh-project"
        started = run_runtime(
            "start", "--project", str(project), "--request", "Deterministic release test.",
            "--synthetic-validation",
        )
        case("a fresh project starts through the runtime", started.returncode == 0)
        decision_trace = run_runtime("decision-trace", "--project", str(project), "--task-id", "release-S1")
        case(
            "the decision-trace surface is read-only and invents no evidence",
            decision_trace.returncode == 0 and "Decision trace" in decision_trace.stdout,
        )
        provider_catalog = run_runtime("decide", "--project", str(project), "--providers")
        case(
            "the decision provider catalog reports declared contracts only",
            provider_catalog.returncode == 0
            and "escalation ladder" in provider_catalog.stdout
            and "no paid call" in provider_catalog.stdout,
        )
        adapter = integration.ConsumerAdapter(
            client, consumer="release-suite/1", required_capabilities=["lifecycle", "approval", "events"],
        )
        envelope = adapter.call("inspect_task", {"project": str(project)})
        case(
            "an inspect operation returns a versioned envelope owned by the engine",
            envelope["schema_version"] == integration.ENVELOPE_SCHEMA
            and envelope["authority"] == "engine"
            and envelope["operation"] == "inspect_task",
        )
        case(
            "inspect returns the parsed run state without granting anything",
            envelope["status"] == "ok" and isinstance(envelope["data"]["state"], dict),
        )
        refused_envelope = adapter.call("approve", {"project": str(project), "approved": True})
        case("an approval without a gate is refused, not inferred from extra fields", refused_envelope["status"] == "refused")
        events = adapter.call("get_events", {"project": str(project)})
        case(
            "the event stream replays through the contract",
            events["status"] == "ok" and isinstance(events["data"]["events"], dict),
        )
        validation = adapter.call("validate", {"project": str(project)})
        case("validation without worker evidence is refused, never fabricated", validation["status"] != "ok")
        try:
            adapter.call("teleport")
            unsupported_refused = False
        except integration.IntegrationError:
            unsupported_refused = True
        case("an unsupported operation is refused before touching state", unsupported_refused)
        case(
            "the contract exposes no operation that records verification",
            "verify" not in integration.OPERATIONS and "record_verification" not in integration.OPERATIONS,
        )

    # ----------------------------------------------------------------- migration
    with workspace() as sandbox:
        project, run_root = make_legacy_run(sandbox, approve=True)
        before = state_bytes(run_root)
        reviewed = migration.plan(run_root)
        case("the plan is explicitly a dry run", reviewed["dry_run"] is True and reviewed["idempotent"] is False)
        ledger_rows = [row for row in reviewed["objects"] if row["path"].endswith("creative-evidence.json")]
        case(
            "the legacy project ledger is classified as readable without transformation",
            ledger_rows and ledger_rows[0]["classification"] == migration.READ_DIRECTLY,
        )
        case(
            "document mirrors are classified legacy read-only",
            any(row["classification"] == migration.LEGACY_READ_ONLY for row in reviewed["objects"]),
        )
        dry = run_runtime("migrate", "--run-root", str(run_root), "--dry-run")
        case("migration dry run reports success", dry.returncode == 0 and "dry run" in dry.stdout)
        case(
            "dry run names the source, target, transformations and backup plan",
            all(token in dry.stdout for token in ("source:", "target:", "transformations on apply", "backup plan")),
        )
        case(
            "dry run writes nothing",
            state_bytes(run_root) == before and not (run_root / "ariadne-run.v1.bak").exists(),
        )
        applied = run_runtime("migrate", "--run-root", str(run_root), "--apply")
        case("migration applies", applied.returncode == 0)
        case(
            "the pre-migration bytes are preserved byte-exact",
            (run_root / "ariadne-run.v1.bak").read_bytes() == before,
        )
        migrated = json.loads(state_bytes(run_root))
        case("migration records the engine contract", migrated["engine"]["contract"] == contracts.ENGINE_CONTRACT)
        case(
            "migration preserves the legacy approval and creates none",
            len(migrated["approvals"]) == 1
            and migrated["approvals"][0]["approval_id"] == "legacy-approval"
            and migrated["migration_history"][-1]["approvals_created"] == 0,
        )
        case(
            "migration invents no review, validation or transition record",
            not any(migrated.get(name) for name in ("reviews", "transitions", "verifications", "capabilities")),
        )
        case("migration writes a durable evidence record", (run_root / migration.REPORT_NAME).is_file())
        after_apply = state_digest(run_root)
        again = run_runtime("migrate", "--run-root", str(run_root), "--apply")
        case(
            "a repeated migration writes nothing",
            again.returncode == 0 and state_digest(run_root) == after_apply and "already current" in again.stdout,
        )
        report = json.loads((run_root / migration.REPORT_NAME).read_text(encoding="utf-8"))
        case("a no-op apply adds no evidence record", len(report["records"]) == 1)
        rolled = run_runtime("migrate", "--run-root", str(run_root), "--rollback")
        case("rollback restores the pre-migration state", rolled.returncode == 0 and state_bytes(run_root) == before)
        case("rollback preserves the migrated state", (run_root / "ariadne-run.v2.bak").is_file())
        report = json.loads((run_root / migration.REPORT_NAME).read_text(encoding="utf-8"))
        case("rollback appends evidence", report["records"][-1]["action"] == "rollback")
        run_runtime("migrate", "--run-root", str(run_root), "--apply")
        state = json.loads(state_bytes(run_root))
        state.setdefault("approvals", []).append({"schema_version": 2, "gate": "G3", "identity": "operator"})
        (run_root / "ariadne-run.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        after_work = state_digest(run_root)
        blocked = run_runtime("migrate", "--run-root", str(run_root), "--rollback")
        case(
            "rollback refuses after v2 work and changes nothing",
            blocked.returncode == 1 and "refused" in blocked.stdout and state_digest(run_root) == after_work,
        )

    with workspace() as sandbox:
        _, run_root = make_legacy_run(sandbox, name="unreadable")
        state_path = run_root / "ariadne-run.json"
        state_path.write_text('{"schema_version": 9, "run_id": "x"}', encoding="utf-8")
        unreadable = run_runtime("migrate", "--run-root", str(run_root), "--apply")
        case(
            "an unreadable schema is refused before any write",
            unreadable.returncode == 1 and "unsupported" in unreadable.stdout
            and not (run_root / "ariadne-run.v9.bak").exists(),
        )
        state_path.write_text('{"schema_version": 1}', encoding="utf-8")
        malformed = run_runtime("migrate", "--run-root", str(run_root), "--apply")
        case("a malformed state is refused before any write", malformed.returncode == 1 and "malformed" in malformed.stdout)

        _, run_root = make_legacy_run(sandbox, name="backup-sentinel")
        sentinel = run_root / "ariadne-run.v1.bak"
        sentinel.write_bytes(b"earlier backup must survive")
        run_runtime("migrate", "--run-root", str(run_root), "--apply")
        case(
            "an existing backup is never overwritten",
            sentinel.read_bytes() == b"earlier backup must survive",
        )

        _, run_root = make_legacy_run(sandbox, name="interrupted")
        leftover = run_root / ".ariadne-run.json.deadbeef.tmp"
        leftover.write_text("{}", encoding="utf-8")
        report = persistence.recovery_report(run_root)
        case(
            "an interrupted write is reported, not repaired",
            report["status"] == "diverged"
            and any(item.get("kind") == "interrupted-write" for item in report["findings"]),
        )

    case(
        "the migration ledger schemas match the runtime scripts",
        _ledger_schemas_match(),
    )
    case(
        "the migration report schema is versioned",
        migration.REPORT_SCHEMA == 1 and migration.REPORT_NAME.endswith(".json"),
    )

    # ------------------------------------------------------------ release facts
    sources = dict(backend.runtime_sources())
    case(
        "the runtime ships the v2 engine modules",
        all(name in sources for name in (
            "src/ariadne_engine/migration.py",
            "src/ariadne_engine/public.py",
            "src/ariadne_engine/integration.py",
            "src/ariadne_engine/release.py",
        )),
    )
    case(
        "the runtime ships the AR-205D decision-intelligence modules",
        all(name in sources for name in (
            "src/ariadne_engine/decisions/compiler.py",
            "src/ariadne_engine/decisions/graph.py",
            "src/ariadne_engine/decisions/planner.py",
            "src/ariadne_engine/decisions/projections.py",
            "src/ariadne_engine/decisions/cache.py",
            "src/ariadne_engine/decisions/escalation.py",
            "src/ariadne_engine/decisions/consensus.py",
            "src/ariadne_engine/decisions/generation.py",
            "src/ariadne_engine/decisions/calibration.py",
            "src/ariadne_engine/decisions/trace.py",
            "src/ariadne_engine/decisions/integrations.py",
            "src/ariadne_engine/decisions/economics.py",
        )),
    )
    case(
        "the runtime excludes maintainer-only trees",
        not any(name.startswith(("validation/", "operations/", "tests/")) for name in sources),
    )
    case(
        "the runtime excludes the release test tooling",
        not any(name in sources for name in (
            "scripts/test-release.py", "scripts/release-check.py", "scripts/test-wheel-install.py",
        )),
    )
    manifest = backend.runtime_manifest(source_commit="fixture-commit")
    from ariadne import cli as launcher_cli
    case("a generated manifest passes the launcher's own validation", launcher_cli.validate_release_manifest(manifest) == [])
    damaged_missing = json.loads(json.dumps(manifest))
    damaged_missing["files"].pop("prompts/project-start.md")
    case("a manifest that omits a required runtime file is refused", launcher_cli.validate_release_manifest(damaged_missing) != [])
    case(
        "the manifest carries the canonical version and a project-state range",
        manifest["version"] == canonical and isinstance(manifest["project_state_schema"]["min"], int),
    )

    with workspace() as sandbox:
        built = backend.build(sandbox / "dist", allow_dirty=True, source_commit="fixture-commit")
        case("local release artifacts build", built["artifact"].is_file() and built["launcher"].is_file())
        problems = release.artifact_problems(sandbox / "dist")
        case("built artifacts match their manifest and checksums", problems == [])
        descriptor_path = sandbox / "dist" / "ariadne-release.json"
        original_descriptor = descriptor_path.read_text(encoding="utf-8")
        descriptor = json.loads(original_descriptor)
        descriptor["sha256"] = "0" * 64
        descriptor_path.write_text(json.dumps(descriptor, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        case("a stale artifact hash fails verification", release.artifact_problems(sandbox / "dist") != [])
        descriptor_path.write_text(original_descriptor, encoding="utf-8")
        case("the restored descriptor passes verification again", release.artifact_problems(sandbox / "dist") == [])

    # ------------------------------------------------- AR-205D decision intelligence
    from ariadne_engine import decisions

    new_operations = (
        "compile_decisions", "compile_decision_graph", "decision_advice", "decision_trace",
        "decision_intelligence_report", "justify_generation", "record_decision_outcome",
        "invalidate_decision_cache",
    )
    case(
        "every AR-205D decision-intelligence operation is exported",
        all(hasattr(api, name) for name in new_operations),
    )
    case(
        "every AR-205D operation carries exactly one stability class",
        all(public.PUBLIC_SURFACE.get(name) == "PROVISIONAL" for name in new_operations),
    )
    case(
        "the decision-intelligence contract and schema are declared and readable",
        contracts.DECISION_INTELLIGENCE_CONTRACT == "ariadne-decision-intelligence-1"
        and contracts.SCHEMA_DECISION_INTELLIGENCE in contracts.READABLE_DECISION_INTELLIGENCE_SCHEMAS,
    )
    case(
        "the decision-intelligence collections are all declared and bounded",
        _collections_are_bounded(),
    )
    case(
        "the classification vocabulary is exactly the declared five",
        contracts.DECISION_CLASSIFICATIONS == ("DETERMINISTIC", "BOUNDED", "GENERATIVE", "HUMAN", "UNRESOLVED"),
    )
    case(
        "an unknown requirement kind classifies UNRESOLVED, never GENERATIVE",
        decisions.compiler.classify_requirement({"kind": "no-such-kind"})["classification"] == "UNRESOLVED",
    )
    projection_problems = [
        problem
        for contract in decisions.projections.CONTRACTS.values()
        for problem in decisions.projections.contract_problems(contract)
    ]
    case(
        "every projection contract declares required fields and no contradiction",
        projection_problems == []
        and all(contract.required for contract in decisions.projections.CONTRACTS.values()),
    )
    case(
        "a missing required projection field is INSUFFICIENT_STATE, never a guess",
        _insufficient_state_is_refused(),
    )
    case(
        "decision confidence still cannot authorize a protected action",
        not decisions.policy.may_act(
            {"status": "answered", "answer_valid": True, "confidence": 0.99,
             "confidence_kind": "CALIBRATED_PROBABILITY"},
            consequence="PROTECTED",
        )["accepted"],
    )
    case(
        "a decision cache key refuses a moving model alias",
        _cache_alias_is_refused(),
    )
    case(
        "the generation gate only accepts declared reasons",
        _undeclared_generation_reason_is_refused(),
    )
    case(
        "the Jev-shaped adapter boundary records live use as NOT_EXECUTED",
        decisions.providers.describe(decisions.providers.JevShapedAdapter())["live_use"] == "NOT_EXECUTED",
    )
    case(
        "the integration surface names four real engine paths",
        len(decisions.integrations.describe()["integrations"]) == 4,
    )

    # ----------------------------------------------------- experimental defaults
    case("the AR-204 experiments are classified as behavior-sensitive", release.experimental_defaults_problems() == [])
    for name in efficiency.BEHAVIOUR_SENSITIVE:
        conservative = efficiency.SETTING_VALUES[name][0]
        case(
            f"experimental flag {name} stays at its conservative default",
            efficiency.DEFAULT_FLAGS.get(name) == conservative and name not in efficiency.SAFE_DEFAULTS,
        )
    state = {"efficiency": {}}
    try:
        efficiency.set_efficiency_config(state, teleportation=True)
        unknown_refused = False
    except contracts.ContractError:
        unknown_refused = True
    case("an unknown experiment flag is refused", unknown_refused)
    try:
        efficiency.set_efficiency_config(state, prompt_profile="compact_v2")
        enabled = state["efficiency"].get("prompt_profile") == "compact_v2"
        still_default = efficiency.DEFAULT_FLAGS.get("prompt_profile") == "legacy"
    except contracts.ContractError:
        enabled = still_default = False
    case(
        "an explicit opt-in records the experiment without changing the default",
        enabled and still_default,
    )

    # ----------------------------------------------------------- gate mutations
    api.__all__.append("smuggled_operation")
    try:
        case("an unclassified export fails the public-surface gate", release.public_surface_problems() != [])
    finally:
        api.__all__.remove("smuggled_operation")
    original_default = efficiency.DEFAULT_FLAGS["prompt_profile"]
    efficiency.DEFAULT_FLAGS["prompt_profile"] = "compact_v2"
    try:
        mutated = release.experimental_defaults_problems()
    finally:
        efficiency.DEFAULT_FLAGS["prompt_profile"] = original_default
    case("a silently promoted experiment fails the gate", mutated != [])
    original_max = integration.MAX_SUPPORTED_VERSION
    integration.MAX_SUPPORTED_VERSION = 0
    try:
        mutated = release.version_problems(ROOT)
    finally:
        integration.MAX_SUPPORTED_VERSION = original_max
    case("a protocol range that excludes its own version fails the gate", mutated != [])

    print("ARIADNE AR-205 RELEASE TEST\n")
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print(f"\n{'FAILED' if failed else 'PASS'}  {len(cases) - len(failed)}/{len(cases)}")
    return 1 if failed else 0


def _ledger_schemas_match() -> bool:
    creative = load_script("ariadne_creative_test", "creative-intelligence.py")
    operations = load_script("ariadne_operations_test", "creative-operations.py")
    return (
        tuple(migration.READABLE_LEDGER_SCHEMAS["creative-evidence.json"]) == tuple(creative.SUPPORTED_SCHEMA_VERSIONS)
        and migration.READABLE_LEDGER_SCHEMAS["creative-operations.json"] == (operations.SCHEMA_VERSION,)
    )


def _collections_are_bounded() -> bool:
    for name in contracts.AR205D_COLLECTIONS:
        try:
            contracts.require_collection_capacity({name: []}, name)
        except contracts.ContractError:
            return False
    try:
        contracts.require_collection_capacity({"not-declared": []}, "not-declared")
    except contracts.ContractError:
        return True
    return False


def _insufficient_state_is_refused() -> bool:
    from ariadne_engine import decisions

    try:
        decisions.projections.build("review-escalation", entries={"stakes": "LOW"})
    except decisions.projections.InsufficientState as exc:
        return "INSUFFICIENT_STATE" in str(exc)
    except Exception:
        return False
    return False


def _cache_alias_is_refused() -> bool:
    from ariadne_engine import decisions

    question = decisions.contracts.DecisionQuestion(
        question_id="q", instructions="Choose.", options=("a", "b"),
    )
    try:
        decisions.cache.key_for(
            question, projection_digest="ab" * 32, provider="p",
            model_version="jev-latest", policy_version="v",
        )
    except contracts.ContractError:
        return True
    return False


def _undeclared_generation_reason_is_refused() -> bool:
    from ariadne_engine import decisions

    try:
        decisions.generation.justify({"run_id": "x"}, reason="because-it-is-fun")
    except contracts.ContractError:
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(self_test())
