"""AR-205 deterministic benchmark cases: release engineering and integration.

The groups follow the AR-205 brief: release metadata, distribution integrity,
migration, the versioned consumer contract, and the golden end-to-end workflows
that represent the product. Every case is offline and drives either the real
runtime scripts or the engine modules the runtime, CLI and API share.

Status semantics match the rest of the suite: pass, fail, observed, error, skip.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from . import fixtures as F
from .cases import Ctx, Outcome, case
from . import design_cases as D
from .ar204_cases import bench_state, make_execution, project_box, verify_task

def runtime(ctx: Ctx):
    return ctx.repo.module("ariadne.py")


def repo_version(ctx: Ctx) -> str:
    return (ctx.repo.root / "VERSION").read_text(encoding="utf-8").strip()


def legacy_run(box, *, approve: bool = False, name: str = "legacy") -> Path:
    run_root = box.run_root
    packet = run_root / f"{name}-S1"
    packet.mkdir(parents=True, exist_ok=True)
    (packet / "manifest.json").write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    state = {
        "schema_version": 1,
        "run_id": name,
        "project": str(box.project),
        "packets": [{"id": f"{name}-S1", "stage": "S1", "path": str(packet)}],
        "next": "Complete the brief.",
    }
    if approve:
        state["approvals"] = [{
            "schema_version": 2, "approval_id": "legacy-approval", "gate": "G1",
            "identity": "previous-operator", "revision": "legacy-revision",
            "recorded_at": "2026-01-01T00:00:00Z",
        }]
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "ariadne-run.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    (box.project / ".ariadne").mkdir(parents=True, exist_ok=True)
    (box.project / ".ariadne" / "creative-evidence.json").write_text(
        json.dumps({"schema_version": 1, "skills": []}), encoding="utf-8"
    )
    box.write("PROJECT.md", "# PROJECT\n\nA legacy project.\n")
    return run_root


# ========================================================== release metadata

@case(
    id="release-metadata.version-surfaces-agree",
    group="release-metadata",
    title="Every repository version surface names the same release",
    task="Check VERSION, pyproject, release notes, install docs and the installation example together.",
    expectation="The engine's version consistency gate reports no disagreements.",
    evaluation="Run the engine release check against the repository root.",
    evidence_required="The problem list for each surface.",
    layer="deterministic",
)
def release_version_surfaces(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    problems = module.ENGINE.release.version_problems(ctx.repo.root)
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"version={repo_version(ctx)}; problems={problems or 'none'}",
        evidence={"version": repo_version(ctx), "problems": problems},
    )


@case(
    id="release-metadata.runtime-reports-version",
    group="release-metadata",
    title="The runtime CLI reports the canonical version",
    task="Run scripts/ariadne.py --version.",
    expectation="The first line names the VERSION file value and the engine contract is printed.",
    evaluation="Compare the output with VERSION.",
    evidence_required="Exit code and both output lines.",
    layer="deterministic",
)
def release_runtime_version(ctx: Ctx) -> Outcome:
    result = ctx.repo.cli("--version")
    expected = f"Ariadne {repo_version(ctx)}"
    contract = runtime(ctx).CONTRACTS.ENGINE_CONTRACT
    ok = result.returncode == 0 and expected in result.stdout and contract in result.stdout
    return Outcome(
        status="pass" if ok else "fail",
        actual=result.tail(3),
        evidence={"exit": result.returncode, "expected": expected, "contract": contract},
    )


@case(
    id="release-metadata.manifest-matches-version",
    group="release-metadata",
    title="The release manifest agrees with VERSION and carries the runtime allowlist",
    task="Build the runtime manifest in memory and compare its version and files with the tree.",
    expectation="The manifest version is VERSION, the project-state range is present, and no private tree is listed.",
    evaluation="Read build-release.runtime_manifest() and inspect the file names.",
    evidence_required="Manifest version, project-state range and the private-path check.",
    layer="deterministic",
)
def release_manifest(ctx: Ctx) -> Outcome:
    backend = ctx.repo.module("build-release.py")
    manifest = backend.runtime_manifest(source_commit="benchmark")
    names = sorted(manifest["files"])
    private = [name for name in names if name.startswith(("validation/", "operations/", "tests/", "private/"))]
    ok = (
        manifest["version"] == repo_version(ctx)
        and manifest["project_state_schema"]["min"] == 1
        and manifest["project_state_schema"]["max"] >= 1
        and not private
        and "scripts/ariadne.py" in manifest["files"]
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"version={manifest['version']}; files={len(names)}; private={private or 'none'}",
        evidence={"schema": manifest["project_state_schema"], "private": private,
                  "has_engine_migration": "src/ariadne_engine/migration.py" in manifest["files"]},
    )


@case(
    id="release-metadata.notes-and-install-docs-name-version",
    group="release-metadata",
    title="Release notes and install docs name the release-candidate version",
    task="Read RELEASE-NOTES.md and the four install documents.",
    expectation="The notes open with the canonical heading and every install document carries the immutable wheel URL.",
    evaluation="Compare the heading and the URL with VERSION.",
    evidence_required="The heading line and the URL check for each document.",
    layer="deterministic",
)
def release_notes_docs(ctx: Ctx) -> Outcome:
    version = repo_version(ctx)
    notes = (ctx.repo.root / "RELEASE-NOTES.md").read_text(encoding="utf-8")
    url = (
        "https://github.com/tanishkfr/ariadne/releases/download/"
        f"v{version}/ariadne-{version}-py3-none-any.whl"
    )
    documents = {}
    for name in ("README.md", "QUICKSTART.md", "INSTALL.md", "GETTING-STARTED.md"):
        text = (ctx.repo.root / name).read_text(encoding="utf-8")
        documents[name] = url in text and "archive/refs/heads/master.zip" not in text
    ok = notes.startswith(f"# Ariadne {version}") and all(documents.values())
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"heading={'ok' if notes.startswith(f'# Ariadne {version}') else notes.splitlines()[0]!r}; docs={documents}",
        evidence={"documents": documents, "url": url},
    )


@case(
    id="release-metadata.contract-and-migration-versions",
    group="release-metadata",
    title="The protocol and migration surfaces carry explicit versions",
    task="Read the engine's integration and migration constants.",
    expectation="The protocol is inside its supported range, the migration target is the record contract, and the report schema is versioned.",
    evaluation="Compare integration.describe() with contracts.SCHEMA_RECORD and migration.REPORT_SCHEMA.",
    evidence_required="Protocol description and migration constants.",
    layer="deterministic",
)
def release_protocol_versions(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    description = module.ENGINE.integration.describe()
    protocol = description["protocol"]
    ok = (
        protocol["min_supported"] <= protocol["version"] <= protocol["max_supported"]
        and description["engine"]["record_schema"] == module.CONTRACTS.SCHEMA_RECORD
        and module.ENGINE.migration.REPORT_SCHEMA >= 1
        and set(module.ENGINE.migration.READABLE_LEDGER_SCHEMAS)
        == {"creative-evidence.json", "creative-operations.json"}
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"protocol {protocol['version']} in {protocol['min_supported']}..{protocol['max_supported']}",
        evidence={"protocol": protocol, "record_schema": description["engine"]["record_schema"]},
    )


@case(
    id="release-metadata.distribution-name-decision-recorded",
    group="release-metadata",
    title="The package-name collision is decided and warned about, not accidental",
    task="Read pyproject.toml and the README compatibility warning.",
    expectation="The distribution name is unchanged, the warning about the GraphQL package is present, and no publication metadata implies a PyPI release.",
    evaluation="Inspect the two files and the release descriptor's publication state.",
    evidence_required="Name, warning token and publication state.",
    layer="deterministic",
)
def release_name_decision(ctx: Ctx) -> Outcome:
    pyproject = (ctx.repo.root / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ctx.repo.root / "README.md").read_text(encoding="utf-8")
    backend = ctx.repo.module("build-release.py")
    publication = backend.publication_state()
    ok = (
        'name = "ariadne"' in pyproject
        and "Ariadne GraphQL" in readme
        and publication["status"] in ("candidate", "blocked")
        and "PyPI" not in pyproject
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"publication={publication['status']}; warning={'Ariadne GraphQL' in readme}",
        evidence={"publication": publication},
    )


# ====================================================== distribution integrity

@case(
    id="release-distribution.artifacts-match-manifest",
    group="release-distribution",
    title="A locally built release directory verifies against its own manifest",
    task="Build the runtime bundle and launcher wheel into the sandbox and verify every digest.",
    expectation="The engine's artifact check reports no problems.",
    evaluation="Run release.artifact_problems() over the built directory.",
    evidence_required="The problem list and the artifact names.",
    layer="deterministic",
)
def distribution_artifacts(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    backend = ctx.repo.module("build-release.py")
    box = ctx.sandbox()
    dist = box.root / "dist"
    built = backend.build(dist, allow_dirty=True, source_commit="benchmark")
    problems = module.ENGINE.release.artifact_problems(dist)
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"artifact={built['artifact'].name}; problems={problems or 'none'}",
        evidence={"artifact": built["artifact"].name, "launcher": built["launcher"].name,
                  "problems": problems},
    )


@case(
    id="release-distribution.stale-artifact-hash-detected",
    group="release-distribution",
    title="A release directory with a stale artifact hash fails verification",
    task="Build artifacts, corrupt the descriptor digest and verify again.",
    expectation="The stale digest is reported as a mismatch.",
    evaluation="Mutate the descriptor and read the problem list.",
    evidence_required="Problem list before and after the mutation.",
    layer="deterministic",
)
def distribution_stale_hash(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    backend = ctx.repo.module("build-release.py")
    box = ctx.sandbox()
    dist = box.root / "dist"
    backend.build(dist, allow_dirty=True, source_commit="benchmark")
    clean = module.ENGINE.release.artifact_problems(dist)
    descriptor_path = dist / "ariadne-release.json"
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    descriptor["sha256"] = "0" * 64
    descriptor_path.write_text(json.dumps(descriptor, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stale = module.ENGINE.release.artifact_problems(dist)
    ok = clean == [] and any("digest does not match" in problem for problem in stale)
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"clean={len(clean)}; stale={stale or 'none'}",
        evidence={"stale": stale},
    )


@case(
    id="release-distribution.launcher-wheel-shape",
    group="release-distribution",
    title="The launcher wheel carries the seed runtime, licence and console entry",
    task="Build the launcher wheel and inspect its contents.",
    expectation="The wheel is named for VERSION, carries ariadne/seed-runtime.zip and the Apache licence, and declares the ariadne entry point.",
    evaluation="Read the wheel's name list and metadata.",
    evidence_required="Wheel name and matching entries.",
    layer="deterministic",
)
def distribution_wheel_shape(ctx: Ctx) -> Outcome:
    backend = ctx.repo.module("build-release.py")
    box = ctx.sandbox()
    dist = box.root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    wheel_path = backend.build_launcher(dist)
    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())
        metadata = ""
        entry_points = ""
        for name in names:
            if name.endswith(".dist-info/METADATA"):
                metadata = wheel.read(name).decode("utf-8", "replace")
            if name.endswith(".dist-info/entry_points.txt"):
                entry_points = wheel.read(name).decode("utf-8", "replace")
    expected = f"ariadne-{repo_version(ctx)}-py3-none-any.whl"
    ok = (
        wheel_path.name == expected
        and "ariadne/seed-runtime.zip" in names
        and any(name.endswith("licenses/LICENSE") for name in names)
        and "ariadne = ariadne.cli:main" in entry_points
        and f"Version: {repo_version(ctx)}" in metadata
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"wheel={wheel_path.name}; entries={len(names)}",
        evidence={"wheel": wheel_path.name, "entry_points": entry_points.strip().splitlines(),
                  "metadata_has_version": f"Version: {repo_version(ctx)}" in metadata},
    )


@case(
    id="release-distribution.experiments-remain-opt-in",
    group="release-distribution",
    title="Behavior-sensitive AR-204 optimizations are still off by default",
    task="Read the efficiency policy defaults and the release gate for them.",
    expectation="Every behavior-sensitive setting keeps its conservative default, and the gate passes.",
    evaluation="Run experimental_defaults_problems() and read DEFAULT_FLAGS.",
    evidence_required="Defaults and the problem list.",
    layer="deterministic",
)
def distribution_experiments(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    problems = module.ENGINE.release.experimental_defaults_problems()
    defaults = {name: module.ENGINE.efficiency.DEFAULT_FLAGS[name]
                for name in module.ENGINE.efficiency.BEHAVIOUR_SENSITIVE}
    ok = not problems and all(
        value == module.ENGINE.efficiency.SETTING_VALUES[name][0] for name, value in defaults.items()
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"defaults={defaults}",
        evidence={"problems": problems, "defaults": defaults},
    )


# ================================================================== migration

@case(
    id="migration.dry-run-writes-nothing",
    group="migration",
    title="The migration dry run reports without writing",
    task="Run the plan over a v1-era run and compare the state bytes with the original.",
    expectation="The plan names the transformations and backup, and no file in the run root changes.",
    evaluation="Snapshot the run root, run the plan, compare digests.",
    evidence_required="Plan fields and the unchanged digest list.",
    layer="deterministic",
)
def migration_dry_run(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = ctx.sandbox()
    run_root = legacy_run(box, approve=True)
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in run_root.iterdir() if path.is_file()}
    reviewed = module.ENGINE.migration.plan(run_root)
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
             for path in run_root.iterdir() if path.is_file()}
    ok = (
        reviewed["dry_run"] is True
        and reviewed["source"]["needs_migration"] is True
        and before == after
        and not (run_root / "ariadne-run.v1.bak").exists()
        and reviewed["expected_post_state"]["approvals_created"] == 0
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"files={sorted(before)}; changed={[name for name in before if before[name] != after.get(name)]}",
        evidence={"plan": {key: reviewed[key] for key in (
            "dry_run", "source", "target", "backup_plan", "expected_post_state")}},
    )


@case(
    id="migration.classification-inventory",
    group="migration",
    title="Every persisted object is classified before migration",
    task="Plan a migration over a fixture with a ledger, a document mirror and a packet manifest.",
    expectation="The run state is MIGRATE, the ledger and manifest are READ_DIRECTLY, and documents are LEGACY_READ_ONLY.",
    evaluation="Read the object classifications.",
    evidence_required="The classification rows.",
    layer="deterministic",
)
def migration_classification(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = ctx.sandbox()
    run_root = legacy_run(box)
    reviewed = module.ENGINE.migration.plan(run_root)
    rows = {row["kind"]: row for row in reviewed["objects"]}
    ok = (
        rows.get("run-state", {}).get("classification") == module.ENGINE.migration.MIGRATE
        and rows.get("project-ledger", {}).get("classification") == module.ENGINE.migration.READ_DIRECTLY
        and rows.get("packet-manifest", {}).get("classification") == module.ENGINE.migration.READ_DIRECTLY
        and rows.get("project-document", {}).get("classification") == module.ENGINE.migration.LEGACY_READ_ONLY
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=", ".join(f"{kind}={row['classification']}" for kind, row in rows.items()),
        evidence={"objects": reviewed["objects"], "unsupported": reviewed["unsupported"]},
    )


@case(
    id="migration.apply-is-additive",
    group="migration",
    title="Migration preserves authority and invents none",
    task="Migrate a v1-era run that carries one legacy approval.",
    expectation="The approval survives unchanged, no new approval or review appears, and the engine marker is recorded.",
    evaluation="Compare the approval list and the migration record before and after.",
    evidence_required="Approval list, migration record, backup digest.",
    layer="deterministic",
)
def migration_apply(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = ctx.sandbox()
    run_root = legacy_run(box, approve=True)
    before = (run_root / "ariadne-run.json").read_bytes()
    module.ENGINE.migration.apply(run_root)
    state = json.loads((run_root / "ariadne-run.json").read_text(encoding="utf-8"))
    record = state["migration_history"][-1]
    ok = (
        (run_root / "ariadne-run.v1.bak").read_bytes() == before
        and len(state["approvals"]) == 1
        and state["approvals"][0]["approval_id"] == "legacy-approval"
        and record["approvals_created"] == 0
        and record["from_record_schema"] == 1
        and state["engine"]["contract"] == module.CONTRACTS.ENGINE_CONTRACT
        and not state.get("reviews") and not state.get("verifications")
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"approvals={len(state['approvals'])}; created={record['approvals_created']}",
        evidence={"record": record, "approvals": state["approvals"]},
    )


@case(
    id="migration.repeated-apply-writes-nothing",
    group="migration",
    title="A repeated migration is a no-op",
    task="Apply the migration twice and compare the state bytes and the evidence records.",
    expectation="The second apply changes nothing and adds no evidence record.",
    evaluation="Digest the state before and after the second apply.",
    evidence_required="State digests and the report record count.",
    layer="deterministic",
)
def migration_idempotent(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = ctx.sandbox()
    run_root = legacy_run(box)
    module.ENGINE.migration.apply(run_root)
    first = (run_root / "ariadne-run.json").read_bytes()
    report_before = json.loads((run_root / module.ENGINE.migration.REPORT_NAME).read_text(encoding="utf-8"))
    outcome = module.ENGINE.migration.apply(run_root)
    second = (run_root / "ariadne-run.json").read_bytes()
    report_after = json.loads((run_root / module.ENGINE.migration.REPORT_NAME).read_text(encoding="utf-8"))
    ok = (
        first == second
        and outcome["evidence"]["migrated"] is False
        and len(report_before["records"]) == len(report_after["records"]) == 1
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"records={len(report_after['records'])}; migrated={outcome['evidence']['migrated']}",
        evidence={"records": report_after["records"]},
    )


@case(
    id="migration.backup-is-never-overwritten",
    group="migration",
    title="An existing backup is preserved rather than replaced",
    task="Place a sentinel at the backup path, then migrate.",
    expectation="The sentinel bytes survive the migration untouched.",
    evaluation="Read the backup file after the apply.",
    evidence_required="Backup bytes.",
    layer="deterministic",
)
def migration_backup_sentinel(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = ctx.sandbox()
    run_root = legacy_run(box)
    sentinel = run_root / "ariadne-run.v1.bak"
    sentinel.write_bytes(b"earlier backup must survive")
    module.ENGINE.migration.apply(run_root)
    ok = sentinel.read_bytes() == b"earlier backup must survive"
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"backup={sentinel.read_bytes()[:32]!r}",
        evidence={"backup": str(sentinel)},
    )


@case(
    id="migration.unreadable-and-malformed-refused",
    group="migration",
    title="Unreadable or malformed legacy state is refused before any write",
    task="Point the migration at an unsupported schema and at a structurally invalid state.",
    expectation="Both refuse and leave the run root untouched.",
    evaluation="Catch the refusals and compare the file list.",
    evidence_required="Refusal texts and the unchanged files.",
    layer="deterministic",
)
def migration_refusals(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = ctx.sandbox()
    run_root = legacy_run(box)
    state_path = run_root / "ariadne-run.json"
    refusals = {}
    for label, payload in (
        ("unreadable", '{"schema_version": 9, "run_id": "x"}'),
        ("malformed", '{"schema_version": 1}'),
    ):
        state_path.write_text(payload, encoding="utf-8")
        try:
            module.ENGINE.migration.apply(run_root)
            refusals[label] = "no refusal"
        except (module.CONTRACTS.ContractError, module.CONTRACTS.StaleSchema) as exc:
            refusals[label] = str(exc)
    ok = (
        "unsupported" in refusals["unreadable"].lower()
        and "malformed" in refusals["malformed"].lower()
        and not (run_root / "ariadne-run.v9.bak").exists()
        and not (run_root / "ariadne-run.v1.bak").exists()
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual="; ".join(refusals.values()),
        evidence={"refusals": refusals},
    )


@case(
    id="migration.rollback-restores-and-preserves",
    group="migration",
    title="Rollback restores the original bytes and preserves the migrated state",
    task="Migrate a v1-era run, then roll back.",
    expectation="The state returns byte-exact to the original and the migrated state is kept as a distinct file.",
    evaluation="Compare digests before, after migration and after rollback.",
    evidence_required="Digests and the preserved file.",
    layer="deterministic",
)
def migration_rollback(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = ctx.sandbox()
    run_root = legacy_run(box, approve=True)
    original = (run_root / "ariadne-run.json").read_bytes()
    module.ENGINE.migration.apply(run_root)
    migrated = (run_root / "ariadne-run.json").read_bytes()
    result = module.ENGINE.migration.rollback(run_root)
    restored = (run_root / "ariadne-run.json").read_bytes()
    preserved = Path(result["preserved"])
    ok = (
        original == restored
        and preserved.is_file()
        and preserved.read_bytes() == migrated
        and original != migrated
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"restored={hashlib.sha256(restored).hexdigest()[:12]}; preserved={preserved.name}",
        evidence={"preserved": result["preserved"], "rollback": result["rollback"]},
    )


@case(
    id="migration.rollback-refuses-after-v2-work",
    group="migration",
    title="Rollback refuses to discard records created under v2",
    task="Migrate, record a v2 approval, then attempt a rollback.",
    expectation="The rollback is refused, the state is unchanged and the pre-migration bytes remain available.",
    evaluation="Read the refusal and compare the state digest.",
    evidence_required="Refusal text, state digest and backup presence.",
    layer="deterministic",
)
def migration_rollback_refusal(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = ctx.sandbox()
    run_root = legacy_run(box)
    module.ENGINE.migration.apply(run_root)
    state = json.loads((run_root / "ariadne-run.json").read_text(encoding="utf-8"))
    state.setdefault("approvals", []).append({"schema_version": 2, "gate": "G3", "identity": "operator"})
    (run_root / "ariadne-run.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    digest = hashlib.sha256((run_root / "ariadne-run.json").read_bytes()).hexdigest()
    refusal = ""
    try:
        module.ENGINE.migration.rollback(run_root)
    except module.CONTRACTS.ContractError as exc:
        refusal = str(exc)
    ok = (
        "refused" in refusal
        and hashlib.sha256((run_root / "ariadne-run.json").read_bytes()).hexdigest() == digest
        and (run_root / "ariadne-run.v1.bak").is_file()
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=refusal or "no refusal",
        evidence={"refusal": refusal, "backup": str(run_root / "ariadne-run.v1.bak")},
    )


@case(
    id="migration.evidence-report-is-durable",
    group="migration",
    title="Apply and rollback each append durable evidence",
    task="Migrate, roll back and read the migration report.",
    expectation="The report holds one apply and one rollback record with the expected digests.",
    evaluation="Read migration-report.json.",
    evidence_required="The evidence records.",
    layer="deterministic",
)
def migration_evidence(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = ctx.sandbox()
    run_root = legacy_run(box)
    module.ENGINE.migration.apply(run_root)
    module.ENGINE.migration.rollback(run_root)
    report = json.loads((run_root / module.ENGINE.migration.REPORT_NAME).read_text(encoding="utf-8"))
    actions = [record["action"] for record in report["records"]]
    roles = {"apply": 0, "rollback": 0}
    for record in report["records"]:
        roles[record["action"]] = roles.get(record["action"], 0) + 1
    ok = actions == ["apply", "rollback"] and roles["apply"] == roles["rollback"] == 1
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"actions={actions}",
        evidence={"records": report["records"]},
    )


@case(
    id="migration.cli-exposes-explicit-actions",
    group="migration",
    title="The migrate command exposes dry run, apply and rollback",
    task="Read the migrate command help text.",
    expectation="All three actions are listed and the dry run is described as the default.",
    evaluation="Run --help for the migrate command.",
    evidence_required="The help text.",
    layer="deterministic",
)
def migration_cli_help(ctx: Ctx) -> Outcome:
    result = ctx.repo.cli("migrate", "--help")
    text = result.combined
    ok = all(token in text for token in ("--dry-run", "--apply", "--rollback", "the default"))
    return Outcome(
        status="pass" if ok else "fail",
        actual=result.tail(4),
        evidence={"help": text},
    )


# ========================================================= integration contract

@case(
    id="integration-contract.negotiation-outcomes",
    group="integration-contract",
    title="Protocol negotiation accepts, refuses and reports unknown fields",
    task="Replay the contract fixtures for a happy path, a future version and an unknown capability.",
    expectation="The happy path accepts, the other two refuse with explicit reasons and unknown fields are only reported.",
    evaluation="Call integration.negotiate() for each fixture.",
    evidence_required="The description and problem lists.",
    layer="deterministic",
)
def integration_negotiation(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    integration = module.ENGINE.integration
    results = {}
    for name, fixture in integration.CONTRACT_FIXTURES.items():
        description, problems = integration.negotiate(fixture)
        results[name] = {"problems": problems, "ignored": description.get("ignored_fields")}
    ok = (
        results["happy_path"]["problems"] == []
        and any("outside the supported range" in problem for problem in results["unsupported_version"]["problems"])
        and any("teleportation" in problem for problem in results["missing_capability"]["problems"])
        and results["unknown_fields"]["problems"] == []
        and set(results["unknown_fields"]["ignored"] or []) >= {"grant_approval", "trust_me"}
        and results["optional_capability_absent"]["problems"] == []
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=json.dumps(results, sort_keys=True)[:300],
        evidence={"results": results},
    )


@case(
    id="integration-contract.describe-names-authority",
    group="integration-contract",
    title="The contract description states where authority lives",
    task="Read integration.describe().",
    expectation="Operations, capabilities, versions and the engine-authority statement are all present.",
    evaluation="Inspect the description.",
    evidence_required="The description.",
    layer="deterministic",
)
def integration_describe(ctx: Ctx) -> Outcome:
    description = runtime(ctx).ENGINE.integration.describe()
    ok = (
        "approve" in description["operations"]
        and "migration" in description["capabilities"]
        and "engine" in description["authority"].lower()
        and description["engine"]["contract"] == runtime(ctx).CONTRACTS.ENGINE_CONTRACT
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"operations={len(description['operations'])}; capabilities={len(description['capabilities'])}",
        evidence={"description": description},
    )


@case(
    id="integration-contract.adapter-envelope",
    group="integration-contract",
    title="Adapter operations return versioned envelopes owned by the engine",
    task="Start a sandbox run and inspect it through the consumer adapter.",
    expectation="The envelope carries the envelope schema, the engine authority marker and the parsed state.",
    evaluation="Call inspect_task through the adapter and read the envelope.",
    evidence_required="The envelope.",
    layer="deterministic",
)
def integration_adapter_envelope(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    client = module.ENGINE.public.EngineClient(module)
    adapter = module.ENGINE.integration.ConsumerAdapter(
        client, consumer="benchmark/1", required_capabilities=["lifecycle", "approval"],
    )
    envelope = adapter.call("inspect_task", {"project": str(box.project)})
    ok = (
        envelope["schema_version"] == module.ENGINE.integration.ENVELOPE_SCHEMA
        and envelope["authority"] == "engine"
        and envelope["status"] == "ok"
        and isinstance(envelope["data"]["state"], dict)
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"status={envelope['status']}; authority={envelope['authority']}",
        evidence={"envelope": {key: envelope[key] for key in ("schema_version", "operation", "status", "authority", "problems")}},
    )


@case(
    id="integration-contract.adapter-refuses-unsupported",
    group="integration-contract",
    title="An unsupported operation is refused explicitly",
    task="Ask the adapter for an operation it does not implement.",
    expectation="An IntegrationError names the supported operations; no state is touched.",
    evaluation="Catch the refusal.",
    evidence_required="The refusal text.",
    layer="deterministic",
)
def integration_adapter_refusal(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    client = module.ENGINE.public.EngineClient(module)
    adapter = module.ENGINE.integration.ConsumerAdapter(client, consumer="benchmark/1")
    refusal = ""
    try:
        adapter.call("teleport")
    except module.ENGINE.integration.IntegrationError as exc:
        refusal = str(exc)
    ok = "unsupported operation" in refusal and "inspect_task" in refusal
    return Outcome(
        status="pass" if ok else "fail",
        actual=refusal or "no refusal",
        evidence={"refusal": refusal},
    )


@case(
    id="integration-contract.no-authority-from-extra-fields",
    group="integration-contract",
    title="Extra payload fields never become authority",
    task="Request an approval with no gate but an approving extra field.",
    expectation="The approval is refused and no approval record is written.",
    evaluation="Read the envelope status and the run state.",
    evidence_required="Envelope status and the approval list.",
    layer="deterministic",
)
def integration_extra_fields(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    client = module.ENGINE.public.EngineClient(module)
    adapter = module.ENGINE.integration.ConsumerAdapter(client, consumer="benchmark/1")
    envelope = adapter.call("approve", {"project": str(box.project), "approved": True, "grant": "G1"})
    approvals = box.state().get("approvals") or []
    ok = envelope["status"] == "refused" and not approvals
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"status={envelope['status']}; approvals={len(approvals)}",
        evidence={"envelope": {key: envelope[key] for key in ("status", "problems")}},
    )


@case(
    id="integration-contract.adapter-cannot-fabricate-validation",
    group="integration-contract",
    title="The contract offers no way to record verification directly",
    task="Read the operation list and attempt validation without worker evidence.",
    expectation="No verification operation exists and validation refuses without evidence.",
    evaluation="Inspect OPERATIONS and call validate.",
    evidence_required="The operation list and the refusal status.",
    layer="deterministic",
)
def integration_no_fabrication(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    client = module.ENGINE.public.EngineClient(module)
    adapter = module.ENGINE.integration.ConsumerAdapter(client, consumer="benchmark/1")
    envelope = adapter.call("validate", {"project": str(box.project)})
    operations = set(module.ENGINE.integration.OPERATIONS)
    ok = (
        "verify" not in operations
        and "record_verification" not in operations
        and envelope["status"] != "ok"
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"status={envelope['status']}; operations={len(operations)}",
        evidence={"operations": sorted(operations), "validate_status": envelope["status"]},
    )


@case(
    id="integration-contract.migration-boundary-visible",
    group="integration-contract",
    title="A consumer can see the migration boundary through the contract",
    task="Point the adapter at a v1-era run and inspect its migration view.",
    expectation="The envelope reports the run as pre-migration without applying anything.",
    evaluation="Call inspect_migration and compare the state bytes.",
    evidence_required="The envelope and the unchanged digest.",
    layer="deterministic",
)
def integration_migration_view(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = ctx.sandbox()
    run_root = legacy_run(box)
    before = (run_root / "ariadne-run.json").read_bytes()
    client = module.ENGINE.public.EngineClient(module)
    adapter = module.ENGINE.integration.ConsumerAdapter(client, consumer="benchmark/1")
    envelope = adapter.call("inspect_migration", {"run_root": str(run_root)})
    ok = (
        envelope["status"] == "ok"
        and "dry run" in envelope["message"]
        and (run_root / "ariadne-run.json").read_bytes() == before
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=envelope["message"].splitlines()[0] if envelope["message"] else "no message",
        evidence={"message": envelope["message"], "problems": envelope["problems"]},
    )


# ============================================================ golden workflows

@case(
    id="golden-workflows.mechanical-task",
    group="golden-workflows",
    title="Workflow A: task, execution, independent validation",
    task="Run the full deterministic S1-to-validated-S4B path for a mechanical task.",
    expectation="The worker result is validated independently with executed commands and an in-contract scope.",
    evaluation="Drive the fixture path and read validation.json.",
    evidence_required="Validation status, independence and command records.",
    layer="deterministic-lifecycle",
)
def golden_mechanical(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    result = ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    validation_path = box.current_packet() / "evidence" / "validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.is_file() else {}
    commands = validation.get("commands", [])
    ok = (
        result.returncode == 0
        and validation.get("status") == "passed"
        and validation.get("independent") is True
        and any(command.get("returncode") is not None for command in commands)
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"validation={validation.get('status')}; commands={len(commands)}",
        evidence={"validation": {key: validation.get(key) for key in ("status", "independent", "scope")},
                  "exit": result.returncode},
    )


@case(
    id="golden-workflows.protected-task",
    group="golden-workflows",
    title="Workflow B: protected task through review and human acceptance",
    task="Validate a build, ingest an independent review, record the human gate and accept once.",
    expectation="Acceptance is refused before the gate, succeeds after it, and the approval cannot be replayed.",
    evaluation="Read the exit codes, lifecycle and consumed approval.",
    evidence_required="Exit codes, lifecycle state and the consumed approval id.",
    layer="deterministic-lifecycle",
)
def golden_protected(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    F.prepare_s5(ctx.repo, box)
    source = box.root / "review.md"
    source.write_text(ctx.fixtures["review"](), encoding="utf-8")
    reviewed = F.ingest_independent_review(ctx.repo, box, source)
    before_gate = ctx.repo.cli("record-acceptance", "--run-root", str(box.run_root), "--outcome", "accepted")
    gate = F.record_g3(ctx.repo, box)
    accepted = ctx.repo.cli("record-acceptance", "--run-root", str(box.run_root), "--outcome", "accepted")
    replay = ctx.repo.cli("record-acceptance", "--run-root", str(box.run_root), "--outcome", "accepted")
    state = box.state()
    consumed = [row for row in state.get("approvals", []) if row.get("gate") == "G3" and row.get("consumed_by")]
    ok = (
        reviewed.returncode == 0
        and before_gate.returncode == 1
        and gate.returncode == 0
        and accepted.returncode == 0
        and replay.returncode == 1
        and state["worker"]["lifecycle"] == "accepted"
        and bool(consumed)
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"lifecycle={state['worker'].get('lifecycle')}; consumed={len(consumed)}",
        evidence={"exit_codes": {"review": reviewed.returncode, "before_gate": before_gate.returncode,
                                 "gate": gate.returncode, "accepted": accepted.returncode,
                                 "replay": replay.returncode},
                  "consumed": [row.get("approval_id") for row in consumed]},
    )


def deliver_return_for_current_role(ctx: Ctx, box) -> Path:
    """Deliver a complete return handoff whose worker role matches the current packet."""
    manifest = box.manifest()
    target = Path(manifest["return_target"])
    role = str((manifest.get("worker") or {}).get("role") or "bulk")
    text = ctx.fixtures["return_handoff"]("complete", manifest["packet_id"])
    text = text.replace("**Worker role:** bulk", f"**Worker role:** {role}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    if not box.exists("QA.md"):
        box.write("QA.md", F.qa_md())
    return target


@case(
    id="golden-workflows.failure-repair",
    group="golden-workflows",
    title="Workflow C: a refused delivery is repaired and then validated",
    task="Deliver a blocked return, let the boundary stop, repair with an escalated worker and validate.",
    expectation="The first delivery is refused without advancing; the escalated repair validates on the second attempt.",
    evaluation="Read the refusal, the packet count and the final validation.",
    evidence_required="Refusal exit code, packet count and validation status.",
    layer="deterministic-lifecycle",
)
def golden_failure_repair(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    packets_before = len(box.packets())
    F.deliver_return(box, ctx.fixtures, status="blocked")
    refused = ctx.repo.cli("advance", "--run-root", str(box.run_root))
    no_progress = len(box.packets()) == packets_before
    escalated = ctx.repo.cli("prepare-next", "--run-root", str(box.run_root), "--escalate")
    deliver_return_for_current_role(ctx, box)
    repaired = ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    validation_path = box.current_packet() / "evidence" / "validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.is_file() else {}
    state = box.state()
    ok = (
        refused.returncode == 2
        and no_progress
        and escalated.returncode == 0
        and repaired.returncode == 0
        and validation.get("status") == "passed"
        and int(state.get("worker", {}).get("attempt", 0)) >= 2
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"refused={refused.returncode}; escalated={escalated.returncode}; "
               f"validation={validation.get('status')}; attempt={state.get('worker', {}).get('attempt')}",
        evidence={"refusal": refused.tail(2), "escalation": escalated.tail(2),
                  "validation_status": validation.get("status"),
                  "worker_role": (box.manifest().get("worker") or {}).get("role")},
    )


@case(
    id="golden-workflows.design-chain",
    group="golden-workflows",
    title="Workflow D: design direction, evidence, critique and bounded refinement",
    task="Walk the design chain from an approved direction to a recorded refinement of a critiqued finding.",
    expectation="The direction is approved, the finding is repaired within its scope and the refinement is verified.",
    evaluation="Build the design chain and read the refinement summary.",
    evidence_required="Direction state, finding state and refinement state.",
    layer="deterministic",
)
def golden_design(ctx: Ctx) -> Outcome:
    box = D.plugin_project(ctx, ctx.case.id)
    module, state, kit, review = D._refinement_state(ctx, box)
    finding_id = review["findings"][0]["finding_id"]
    proposal = module.CRITIQUE.propose_refinement(state, finding_id, **D._proposal(kit, review))
    applied = module.CRITIQUE.record_refinement(
        state, proposal["refinement_id"], applied=True,
        changed_artifacts=["src/styles/landing.css"],
        revalidated={"npm test": "42 passed"},
        recaptured=[kit["evidence"]["evidence_id"]],
        regressions=[],
    )
    module.CRITIQUE.resolve_findings(state, proposal["refinement_id"], resolved=[])
    finding = module.CRITIQUE.finding(state, finding_id)
    summary = module.CRITIQUE.refinement_summary(state, task_id="bench-S4B")
    direction = kit["direction"]
    ok = (
        module.DESIGN.direction_revision(direction) == review["direction_revision"]
        and kit["evidence"].get("evidence_id")
        and applied["state"] == "verified"
        and str(finding.get("state")) == "repaired"
        and summary.get("resolved") == 1
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"refinement={applied['state']}; finding={finding.get('state')}",
        evidence={"refinement": {key: applied.get(key) for key in ("refinement_id", "state", "finding_id")},
                  "summary": summary},
    )


@case(
    id="golden-workflows.decision-plane",
    group="golden-workflows",
    title="Workflow E: bounded decision, policy, execution and verification",
    task="Evaluate one deterministic decision, record its action, then verify the task it informed.",
    expectation="The decision is bounded, has no authorization effect, the action edge is recorded and verification reaches VERIFIED.",
    evaluation="Read the decision record, the action edge and the verification status.",
    evidence_required="Decision record, action record and verification record.",
    layer="deterministic",
)
def golden_decision(ctx: Ctx) -> Outcome:
    from .ar203_cases import choice_question

    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = module.DECISIONS.providers.DeterministicProvider(
        script={"failure-class": {"answer": "TIMEOUT", "confidence": 0.8,
                                  "confidence_kind": "DERIVED_CONFIDENCE"}},
    )
    projection = module.DECISIONS.batch.project(entries={"command": {"timed_out": True}})
    batch = module.DECISIONS.batch.evaluate(
        state, questions=[choice_question(module)], projection=projection,
        provider=provider, task_id="bench-S4B",
    )
    decision = module.DECISIONS.batch.decision(state, batch["results"][0]["decision_id"])
    execution = make_execution(module, state)
    actioned = module.DECISIONS.batch.mark_acted_on(
        state, decision["decision_id"], action="repair",
    )
    record, observer, verifier = verify_task(module, box, state, subject="bench-S4B")
    trace = module.DECISIONS.batch.trace(state, task_id="bench-S4B")
    ok = (
        decision["status"] == "answered"
        and decision["authorization_effect"] == "none"
        and actioned.get("acted_on") is True
        and record["level"] == "VERIFIED"
        and bool(trace)
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"decision={decision['status']}; level={record['level']}; trace={len(trace)}",
        evidence={"decision": {key: decision.get(key) for key in ("decision_id", "status", "answer", "authorization_effect")},
                  "action": {key: actioned.get(key) for key in ("acted_on", "resulting_action")},
                  "verification_level": record["level"]},
    )


@case(
    id="golden-workflows.migration-cli",
    group="golden-workflows",
    title="Workflow F: dry run, migrate, validate and roll back through the CLI",
    task="Run the migrate command over a v1-era fixture and validate every step.",
    expectation="Dry run writes nothing, apply preserves the original and rollback restores it, with evidence at every step.",
    evaluation="Drive the CLI and compare digests.",
    evidence_required="Exit codes, digests and the migration report.",
    layer="deterministic",
)
def golden_migration_cli(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    report_name = module.ENGINE.migration.REPORT_NAME
    box = ctx.sandbox()
    run_root = legacy_run(box, approve=True)
    original = (run_root / "ariadne-run.json").read_bytes()
    dry = ctx.repo.cli("migrate", "--run-root", str(run_root), "--dry-run")
    unchanged = (run_root / "ariadne-run.json").read_bytes() == original
    applied = ctx.repo.cli("migrate", "--run-root", str(run_root), "--apply")
    migrated_state = json.loads((run_root / "ariadne-run.json").read_text(encoding="utf-8"))
    rolled = ctx.repo.cli("migrate", "--run-root", str(run_root), "--rollback")
    restored = (run_root / "ariadne-run.json").read_bytes() == original
    report = json.loads((run_root / report_name).read_text(encoding="utf-8"))
    ok = (
        dry.returncode == 0
        and unchanged
        and applied.returncode == 0
        and migrated_state["engine"]["contract"] == runtime(ctx).CONTRACTS.ENGINE_CONTRACT
        and rolled.returncode == 0
        and restored
        and [record["action"] for record in report["records"]] == ["apply", "rollback"]
    )
    return Outcome(
        status="pass" if ok else "fail",
        actual=f"dry={dry.returncode}; apply={applied.returncode}; rollback={rolled.returncode}; restored={restored}",
        evidence={"digests": {"original": hashlib.sha256(original).hexdigest()[:12],
                              "restored": hashlib.sha256((run_root / "ariadne-run.json").read_bytes()).hexdigest()[:12]},
                  "actions": [record["action"] for record in report["records"]]},
    )
