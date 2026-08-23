#!/usr/bin/env python3
"""Adversarial install/update/rollback/doctor/uninstall controls for V1.4."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from builderos import cli  # noqa: E402


def load_release_tool():
    path = ROOT / "scripts" / "build-release.py"
    spec = importlib.util.spec_from_file_location("builderos_release_tool", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("release tool could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RELEASE = load_release_tool()


@contextlib.contextmanager
def workspace():
    path = ROOT / "validation" / f"distribution-self-test-{uuid.uuid4().hex}"
    path.mkdir()
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


def make_bundle(output: Path, version: str, minimum_bootstrap: str = "1.4.0") -> Path:
    output.mkdir(parents=True, exist_ok=True)
    file_bytes = {
        relative: path.read_bytes()
        for relative, path in RELEASE.runtime_sources()
    }
    file_bytes["VERSION"] = (version + "\n").encode("utf-8")
    manifest = {
        "schema_version": 1,
        "product": "Builder OS",
        "version": version,
        "source_commit": f"fixture-{version}",
        "minimum_bootstrap_version": minimum_bootstrap,
        "project_state_schema": {"min": 1, "max": 1},
        "files": {
            relative: hashlib.sha256(content).hexdigest()
            for relative, content in sorted(file_bytes.items())
        },
    }
    bundle = output / f"builder-os-runtime-{version}.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        for relative, content in sorted(file_bytes.items()):
            RELEASE.zip_entry(archive, relative, content)
        RELEASE.zip_entry(
            archive,
            cli.RUNTIME_MANIFEST,
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
    return bundle


def local_descriptor(path: Path, bundle: Path, version: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product": "Builder OS",
                "version": version,
                "artifact": bundle.name,
                "sha256": cli.sha256(bundle),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def self_test() -> int:
    cases: list[tuple[str, bool]] = []

    def case(name: str, passed: bool) -> None:
        cases.append((name, bool(passed)))

    path_env = {"LOCALAPPDATA": "C:/Users/Person/AppData/Local"}
    case(
        "Windows uses a user-local data directory",
        cli.user_data_home("Windows", path_env, Path("C:/Users/Person")).as_posix().endswith("AppData/Local/BuilderOS"),
    )
    case(
        "macOS uses Application Support",
        cli.user_data_home("Darwin", {}, Path("/Users/person")).as_posix().endswith(
            "/Users/person/Library/Application Support/BuilderOS"
        ),
    )
    case(
        "Linux honours XDG data home",
        cli.user_data_home(
            "Linux", {"XDG_DATA_HOME": "/data/person"}, Path("/home/person")
        ).as_posix().endswith("/data/person/builderos"),
    )

    replace_attempts = []

    def transient_replace(_source: Path, _target: Path) -> None:
        replace_attempts.append(1)
        if len(replace_attempts) < 3:
            raise PermissionError("fixture sharing violation")

    cli.replace_with_retry(
        Path("fixture.tmp"), Path("fixture.json"), attempts=3,
        replace=transient_replace, sleep=lambda _delay: None,
    )
    case("launcher atomic writes retry transient sharing violations", len(replace_attempts) == 3)
    try:
        cli.replace_with_retry(
            Path("fixture.tmp"), Path("fixture.json"), attempts=2,
            replace=lambda _source, _target: (_ for _ in ()).throw(
                PermissionError("fixture persistent denial")
            ),
            sleep=lambda _delay: None,
        )
        persistent_replace_failed = False
    except PermissionError:
        persistent_replace_failed = True
    case("launcher atomic writes expose persistent denial", persistent_replace_failed)

    with workspace() as root:
        release_dir = root / "release"
        bundle_140 = make_bundle(release_dir, "1.4.0")
        bundle_141 = make_bundle(release_dir, "1.4.1")
        incompatible_bundle = make_bundle(release_dir, "1.5.0", "99.0.0")
        descriptor_141 = local_descriptor(release_dir / "release-141.json", bundle_141, "1.4.1")
        legacy_manifest = cli.bundle_manifest(bundle_140)
        for relative in cli.V151_REQUIRED_RUNTIME_FILES:
            legacy_manifest["files"].pop(relative, None)
        case(
            "new launcher accepts a pre-Claude rollback manifest",
            not cli.validate_release_manifest(legacy_manifest),
        )
        current_without_reasoner = json.loads(json.dumps(legacy_manifest))
        current_without_reasoner["version"] = "1.5.1"
        case(
            "V1.5.1 manifest cannot omit its reasoner runtime",
            any(
                "required runtime files" in problem
                for problem in cli.validate_release_manifest(current_without_reasoner)
            ),
        )
        home = root / "user-data"
        target = root / "personal-skills" / "builderos"
        project = root / "person-project"
        project.mkdir()
        sentinel = project / "existing-site.txt"
        sentinel.write_text("person-owned\n", encoding="utf-8")
        sentinel_hash = cli.sha256(sentinel)

        pointer_140 = cli.install_bundle(bundle_140, home, target)
        runtime_140 = Path(pointer_140["runtime_root"])
        case("fresh user installs a self-contained runtime", not cli.runtime_problems(runtime_140))
        runtime_help = subprocess.run(
            [sys.executable, str(runtime_140 / "scripts" / "builderos.py"), "--help"],
            capture_output=True,
            text=True,
        )
        case(
            "running the installed controller preserves the immutable runtime",
            runtime_help.returncode == 0 and not cli.runtime_problems(runtime_140),
        )
        case("fresh install registers one managed skill", not cli.skill_problems(runtime_140, target))
        claude_target = root / "optional-claude-skills" / "builderos"
        case("normal installation does not enable Claude", not claude_target.exists())
        cli.configure_claude_reasoner(
            home, claude_target, "install", require_cli=False
        )
        case(
            "explicit Claude enable installs only the optional entry skill",
            (claude_target / cli.CLAUDE_SKILL_MARKER).is_file()
            and not (project / "CLAUDE.md").exists()
            and not cli.runtime_problems(runtime_140),
        )
        cli.configure_claude_reasoner(
            home, claude_target, "uninstall", require_cli=False
        )
        case(
            "Claude disable restores the Codex-only installed state",
            not claude_target.exists() and not cli.skill_problems(runtime_140, target),
        )
        case("installation does not contaminate a project", cli.sha256(sentinel) == sentinel_hash and len(list(project.iterdir())) == 1)
        case("installed runtime does not depend on the source checkout", str(ROOT).lower() not in (target / cli.SKILL_INSTALLATION).read_text(encoding="utf-8").lower())

        (target / "SKILL.md").unlink()
        case("doctor detects a corrupted skill", any(status == "problem" and label == "Codex skill" for status, label, _ in cli.doctor(home, target)[1]))
        cli.repair_current(home, target)
        case("reinstall repairs managed skill drift", not cli.skill_problems(runtime_140, target))
        case("second install remains idempotent", cli.repair_current(home, target)["version"] == "1.4.0")

        (runtime_140 / "ROUTER.md").unlink()
        try:
            cli.repair_damaged_runtime(
                cli.current_install(home), home, target, str(descriptor_141)
            )
            silent_upgrade_blocked = False
        except cli.ProductError:
            silent_upgrade_blocked = True
        case(
            "repair never silently upgrades or downgrades a damaged runtime",
            silent_upgrade_blocked and cli.current_install(home)["version"] == "1.4.0",
        )
        cli.install_bundle(bundle_140, home, target)
        case("same-version bundle repairs damaged runtime", not cli.runtime_problems(runtime_140))

        config = home / "config.json"
        config.write_text('{"voice":"calm"}\n', encoding="utf-8")
        try:
            cli.install_bundle(bundle_141, home, target, failure_at="after-runtime")
            interrupted_blocked = False
        except cli.ProductError:
            interrupted_blocked = True
        case("interrupted update leaves current version active", interrupted_blocked and cli.current_install(home)["version"] == "1.4.0")
        case("interrupted update leaves skill compatible", not cli.skill_problems(runtime_140, target))

        try:
            cli.install_bundle(bundle_141, home, target, failure_at="after-skill")
            pointer_failure_blocked = False
        except cli.ProductError:
            pointer_failure_blocked = True
        case("pointer failure restores previous skill", pointer_failure_blocked and not cli.skill_problems(runtime_140, target))

        pointer_141 = cli.install_bundle(bundle_141, home, target)
        runtime_141 = Path(pointer_141["runtime_root"])
        case("update activates the new verified runtime", pointer_141["version"] == "1.4.1" and not cli.runtime_problems(runtime_141))
        case("update keeps the rollback version", runtime_140.is_dir())
        case("update preserves user configuration", config.read_text(encoding="utf-8") == '{"voice":"calm"}\n')
        case("updated skill points to the new runtime", not cli.skill_problems(runtime_141, target))

        hidden_runtime = runtime_141.with_name("1.4.1-hidden")
        runtime_141.replace(hidden_runtime)
        try:
            _, missing_runtime_checks = cli.doctor(home, target)
        finally:
            hidden_runtime.replace(runtime_141)
        case(
            "doctor detects a missing active runtime",
            any(label == "Runtime" and status == "problem" for status, label, _ in missing_runtime_checks),
        )

        try:
            cli.install_bundle(incompatible_bundle, home, target)
            launcher_mismatch_blocked = False
        except cli.ProductError:
            launcher_mismatch_blocked = True
        case(
            "incompatible launcher requirement is rejected",
            launcher_mismatch_blocked and cli.current_install(home)["version"] == "1.4.1",
        )

        rolled_back = cli.rollback(home, target)
        case("rollback restores the previous runtime and skill", rolled_back["version"] == "1.4.0" and not cli.skill_problems(runtime_140, target))
        case("rollback preserves project files", cli.sha256(sentinel) == sentinel_hash)

        bad_checksum = root / "bad-checksum.zip"
        shutil.copyfile(bundle_141, bad_checksum)
        try:
            cli.install_bundle(bad_checksum, home, target, expected_sha="0" * 64)
            checksum_blocked = False
        except cli.ProductError:
            checksum_blocked = True
        case("checksum mismatch is rejected before extraction", checksum_blocked and cli.current_install(home)["version"] == "1.4.0")

        traversal = root / "traversal.zip"
        with zipfile.ZipFile(traversal, "w") as archive:
            archive.writestr("../outside.txt", "unsafe")
        try:
            cli.install_bundle(traversal, home, target)
            traversal_blocked = False
        except cli.ProductError:
            traversal_blocked = True
        case("archive path traversal is rejected", traversal_blocked and not (root / "outside.txt").exists())

        before_failure = cli.current_install(home)["version"]
        try:
            cli.release_descriptor(str(root / "missing-release.json"))
            network_failure_clear = False
        except cli.ProductError as exc:
            network_failure_clear = "Could not read release source" in str(exc)
        case("unavailable update source fails clearly", network_failure_clear and cli.current_install(home)["version"] == before_failure)

        run_root = root / "person-project-builderos"
        run_root.mkdir()
        (run_root / "builderos-run.json").write_text(
            json.dumps({"schema_version": 1, "project": str(project.resolve())}) + "\n",
            encoding="utf-8",
        )
        code, checks = cli.doctor(home, target, project)
        case("doctor recognises compatible existing project state", code == 0 and any(label == "Project" and status == "ok" for status, label, _ in checks))
        (run_root / "builderos-run.json").write_text(
            json.dumps({"schema_version": 99, "project": str(project.resolve())}) + "\n",
            encoding="utf-8",
        )
        code, checks = cli.doctor(home, target, project)
        case("doctor blocks an incompatible project-state version", code == 2 and any(label == "Project" and status == "problem" for status, label, _ in checks))

        original_path = os.environ.get("PATH")
        os.environ["PATH"] = ""
        try:
            _, missing_codex_checks = cli.doctor(home, target)
        finally:
            if original_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = original_path
        case("doctor reports missing Codex without corrupting installation", any(label == "Codex" and status == "warning" for status, label, _ in missing_codex_checks))

        output = io.StringIO()
        with redirect_stdout(output):
            code = cli.main([
                "--data-home", str(home), "--skill-home", str(target),
                "update", "--manifest", str(descriptor_141),
            ])
        case("CLI update consumes a release description", code == 0 and cli.current_install(home)["version"] == "1.4.1")
        case("normal update output avoids internal workflow jargon", not any(token in output.getvalue() for token in ("S4B", "packet", "manifest", "adapter")))

        original_atomic = cli.atomic_json
        cli.atomic_json = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            PermissionError("fixture denied")
        )
        permission_output = io.StringIO()
        try:
            with redirect_stdout(permission_output):
                permission_code = cli.main([
                    "--data-home", str(home), "--skill-home", str(target),
                    "rollback",
                ])
        finally:
            cli.atomic_json = original_atomic
        case(
            "permission failure is plain and preserves the active version",
            permission_code == 2
            and "permission or filesystem error" in permission_output.getvalue()
            and cli.current_install(home)["version"] == "1.4.1"
            and not cli.skill_problems(runtime_141, target),
        )

        user_extra = target / "personal-note.txt"
        user_extra.write_text("keep me\n", encoding="utf-8")
        try:
            cli.repair_current(home, target)
            user_file_preserved = False
        except cli.ProductError:
            user_file_preserved = user_extra.is_file()
        case("repair never deletes a user file from the skill directory", user_file_preserved)
        user_extra.unlink()

        removed = cli.uninstall(home, target)
        case("uninstall removes runtime and managed skill", not home.exists() and not target.exists() and len(removed) == 2)
        case("uninstall preserves every project file", cli.sha256(sentinel) == sentinel_hash and (run_root / "builderos-run.json").is_file())

        unmanaged_home = root / "unmanaged-home"
        unmanaged_target = root / "unmanaged-skills" / "builderos"
        unmanaged_target.mkdir(parents=True)
        (unmanaged_target / "SKILL.md").write_text("person-owned\n", encoding="utf-8")
        try:
            cli.install_bundle(bundle_140, unmanaged_home, unmanaged_target)
            unmanaged_blocked = False
        except cli.ProductError:
            unmanaged_blocked = True
        case("installer refuses to overwrite an unmanaged skill", unmanaged_blocked and (unmanaged_target / "SKILL.md").read_text(encoding="utf-8") == "person-owned\n")

    print("BUILDER OS DISTRIBUTION SELF-TEST\n")
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print(f"\n{'FAILED' if failed else 'PASS'}  {len(cases) - len(failed)}/{len(cases)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(self_test())
