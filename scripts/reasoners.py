#!/usr/bin/env python3
"""Provider-neutral reasoner selection, detection, and continuity evidence."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "adapters" / "reasoners.json"
SCHEMA_VERSION = 1
EVIDENCE_CLASSES = (
    "verified", "reasonably-assumed", "externally-unverified", "blocked"
)
CONTINUITY_KINDS = ("reasoner-switch", "reasoner-failure")
CLAUDE_SKILL = ROOT / "adapters" / "claude-reasoner-skill" / "SKILL.md"
FLOW_FIXTURES = ROOT / "validation" / "fixtures" / "v1.5.1-reasoner-flows.json"


class ReasonerError(RuntimeError):
    pass


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_contract(path: Path = CONTRACT_PATH) -> dict:
    try:
        value = json.loads(read(path))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReasonerError(f"Reasoner adapter contract is unreadable: {exc}") from exc
    problems = contract_problems(value)
    if problems:
        raise ReasonerError("Reasoner adapter contract is invalid: " + "; ".join(problems))
    return value


def contract_problems(value: dict | None = None) -> list[str]:
    if value is None:
        try:
            value = json.loads(read(CONTRACT_PATH))
        except (OSError, json.JSONDecodeError) as exc:
            return [f"reasoner contract unreadable: {exc}"]
    problems = []
    if value.get("schema_version") != SCHEMA_VERSION:
        problems.append("reasoner contract has wrong schema version")
    providers = value.get("providers")
    if not isinstance(providers, dict):
        return problems + ["reasoner contract has no providers"]
    if value.get("default") != "codex":
        problems.append("Codex must remain the default reasoner")
    expected_stages = ["S1", "S2", "S3", "S4A", "S5", "S6"]
    if value.get("reasoning_stages") != expected_stages:
        problems.append("reasoning stage set drifted or includes S4B")
    for identifier in ("codex", "claude"):
        provider = providers.get(identifier)
        if not isinstance(provider, dict):
            problems.append(f"reasoner provider missing: {identifier}")
            continue
        adapter = ROOT / str(provider.get("adapter", ""))
        if not adapter.is_file():
            problems.append(f"reasoner adapter missing: {identifier}")
        capabilities = provider.get("capabilities")
        if not isinstance(capabilities, dict) or not capabilities:
            problems.append(f"reasoner capabilities missing: {identifier}")
        elif any(status not in EVIDENCE_CLASSES for status in capabilities.values()):
            problems.append(f"reasoner capability has invalid evidence class: {identifier}")
    codex = providers.get("codex", {})
    if codex.get("entry") != "embedded" or codex.get("opt_in") is not False:
        problems.append("Codex default entry contract drifted")
    claude = providers.get("claude", {})
    if (
        claude.get("entry") != "external-cli"
        or claude.get("opt_in") is not True
        or claude.get("executable") != "claude"
        or claude.get("version_args") != ["--version"]
    ):
        problems.append("Claude must remain an opt-in detected CLI adapter")
    if set(codex.get("capabilities", {})) != set(claude.get("capabilities", {})):
        problems.append("reasoner capability matrix rows do not match")
    problems.extend(skill_contract_problems())
    return problems


def skill_contract_problems(text: str | None = None) -> list[str]:
    problems = []
    try:
        text = text if text is not None else read(CLAUDE_SKILL)
    except OSError as exc:
        return [f"optional Claude reasoner skill is unreadable: {exc}"]
    for token in (
        "scripts/builderos.py",
        "reasoner-status",
        "select-reasoner",
        "record-reasoner-failure",
        "Never grant a gate",
        "S4B",
        "isolated S5",
        "not create a project `CLAUDE.md`",
        "## Stop conditions",
    ):
        if token not in text:
            problems.append(f"optional Claude reasoner skill missing boundary: {token}")
    return problems


def fixture_problems(value: dict | None = None, runtime_text: str | None = None) -> list[str]:
    problems = []
    if value is None:
        try:
            value = json.loads(read(FLOW_FIXTURES))
        except (OSError, json.JSONDecodeError) as exc:
            return [f"reasoner flow fixtures are unreadable: {exc}"]
    fixtures = value.get("fixtures", [])
    expected = {
        "simple website",
        "portfolio-quality interactive experience",
        "existing messy project",
        "project with a rejected design direction",
        "project with a partial implementation return",
    }
    if value.get("schema_version") != 1:
        problems.append("reasoner flow fixture schema is wrong")
    if value.get("evidence_class") != "structural fixture; no live Claude execution":
        problems.append("reasoner fixtures overstate their evidence class")
    if len(fixtures) != 5 or {item.get("archetype") for item in fixtures} != expected:
        problems.append("reasoner fixtures do not cover the five required project shapes")
    directions = {(item.get("initial_reasoner"), item.get("next_reasoner")) for item in fixtures}
    if not {("codex", "claude"), ("claude", "codex")}.issubset(directions):
        problems.append("reasoner fixtures do not cover both provider switch directions")
    runtime_text = runtime_text if runtime_text is not None else read(ROOT / "scripts" / "builderos.py")
    for item in fixtures:
        label = str(item.get("runtime_test", "")).strip()
        if not label or label not in runtime_text:
            problems.append(f"reasoner fixture has no executable runtime control: {item.get('id')}")
    return problems


def provider(identifier: str, contract: dict | None = None) -> dict:
    contract = contract or load_contract()
    value = contract["providers"].get(identifier)
    if not value:
        raise ReasonerError(f"Unknown reasoner: {identifier}")
    return value


def selected(state: dict, contract: dict | None = None) -> dict:
    contract = contract or load_contract()
    current = state.get("reasoner")
    if isinstance(current, dict) and current.get("id") in contract["providers"]:
        return current
    return {
        "id": contract["default"],
        "reason": "V1.5 default; legacy run has no explicit reasoner metadata.",
        "classification": "verified",
        "availability": "embedded",
        "version": "Builder OS orchestrator",
    }


def detect(
    identifier: str,
    contract: dict | None = None,
    which=shutil.which,
    runner=subprocess.run,
) -> dict:
    contract = contract or load_contract()
    definition = provider(identifier, contract)
    if definition["entry"] == "embedded":
        return {
            "id": identifier,
            "availability": "embedded",
            "classification": "verified",
            "version": "Builder OS orchestrator",
            "executable": "not required",
            "execution": "available in the current orchestrator",
        }
    executable = which(definition["executable"])
    if not executable:
        return {
            "id": identifier,
            "availability": "unavailable",
            "classification": "blocked",
            "version": "not observed",
            "executable": "not found",
            "execution": "not run",
        }
    try:
        result = runner(
            [str(executable), *definition["version_args"]],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "id": identifier,
            "availability": "unavailable",
            "classification": "blocked",
            "version": "not observed",
            "executable": str(executable),
            "execution": f"version check failed: {type(exc).__name__}",
        }
    version = (result.stdout or result.stderr).strip().splitlines()
    if result.returncode != 0 or not version:
        return {
            "id": identifier,
            "availability": "unavailable",
            "classification": "blocked",
            "version": "not observed",
            "executable": str(executable),
            "execution": f"version check exited {result.returncode}",
        }
    return {
        "id": identifier,
        "availability": "detected",
        "classification": "reasonably-assumed",
        "version": version[0],
        "executable": str(executable),
        "execution": "CLI detected; authentication and Builder OS execution unverified",
    }


def selectable(capability: dict) -> bool:
    return capability.get("availability") in ("embedded", "detected")


def selection_record(
    identifier: str,
    reason: str,
    capability: dict,
    recorded_at: str,
    status: str = "selected",
) -> dict:
    reason = reason.strip()
    if not reason:
        raise ReasonerError("Reasoner selection needs a concrete reason")
    if capability.get("id") != identifier:
        raise ReasonerError("Reasoner capability does not match the selection")
    if status not in ("selected", "blocked", "fallback"):
        raise ReasonerError(f"Unsupported reasoner selection status: {status}")
    return {
        "id": identifier,
        "reason": reason,
        "status": status,
        "recorded_at": recorded_at,
        "classification": capability.get("classification", "blocked"),
        "availability": capability.get("availability", "unavailable"),
        "version": capability.get("version", "not observed"),
        "executable": capability.get("executable", "not observed"),
        "execution": capability.get("execution", "not observed"),
    }


def continuity_record(
    kind: str,
    packet_id: str,
    stage: str,
    from_reasoner: str,
    to_reasoner: str | None,
    summary: str,
    evidence_class: str,
    recorded_at: str,
) -> dict:
    if kind not in CONTINUITY_KINDS:
        raise ReasonerError(f"Unsupported reasoner continuity kind: {kind}")
    if evidence_class not in EVIDENCE_CLASSES:
        raise ReasonerError(f"Unsupported reasoner evidence class: {evidence_class}")
    if not summary.strip():
        raise ReasonerError("Reasoner continuity evidence needs a summary")
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "packet_id": packet_id,
        "stage": stage,
        "from_reasoner": from_reasoner,
        "to_reasoner": to_reasoner,
        "summary": summary.strip(),
        "evidence_class": evidence_class,
        "recorded_at": recorded_at,
        "provider_execution": "not inferred from this continuity record",
        "gate_effect": "none",
    }


def continuity_problems(path: Path, parent: dict) -> list[str]:
    try:
        value = json.loads(read(path))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid reasoner continuity evidence: {exc}"]
    problems = []
    if value.get("schema_version") != SCHEMA_VERSION:
        problems.append("reasoner continuity evidence has wrong schema version")
    if value.get("kind") not in CONTINUITY_KINDS:
        problems.append("reasoner continuity evidence has unknown kind")
    if value.get("packet_id") != parent.get("packet_id"):
        problems.append("reasoner continuity evidence has wrong packet ID")
    if value.get("stage") != parent.get("stage"):
        problems.append("reasoner continuity evidence has wrong stage")
    if not str(value.get("from_reasoner", "")).strip():
        problems.append("reasoner continuity evidence has no source reasoner")
    if value.get("kind") == "reasoner-switch" and not str(value.get("to_reasoner", "")).strip():
        problems.append("reasoner switch evidence has no target reasoner")
    if not str(value.get("summary", "")).strip():
        problems.append("reasoner continuity evidence has no summary")
    if value.get("evidence_class") not in EVIDENCE_CLASSES:
        problems.append("reasoner continuity evidence has invalid evidence class")
    if value.get("gate_effect") != "none":
        problems.append("reasoner continuity evidence cannot affect a gate")
    return problems


def self_test() -> int:
    cases = []

    def case(name: str, passed: bool) -> None:
        cases.append((name, passed))

    contract = load_contract()
    case("reasoner contract passes (positive control)", not contract_problems(contract))
    changed = json.loads(json.dumps(contract))
    changed["default"] = "claude"
    case("Claude cannot become the default", bool(contract_problems(changed)))
    changed = json.loads(json.dumps(contract))
    changed["reasoning_stages"].append("S4B")
    case("reasoner contract cannot absorb implementation", bool(contract_problems(changed)))
    changed = json.loads(json.dumps(contract))
    changed["providers"]["claude"]["capabilities"]["handoff"] = "magic"
    case("unknown capability evidence state is rejected", bool(contract_problems(changed)))
    changed = json.loads(json.dumps(contract))
    del changed["providers"]["claude"]["capabilities"]["handoff"]
    case("capability matrix row drift is rejected", bool(contract_problems(changed)))
    skill = read(CLAUDE_SKILL)
    case("optional Claude skill contract passes (positive control)", not skill_contract_problems(skill))
    case(
        "optional Claude skill cannot lose the failure boundary",
        bool(skill_contract_problems(skill.replace("record-reasoner-failure", "continue-anyway", 1))),
    )
    fixture_value = json.loads(read(FLOW_FIXTURES))
    runtime_text = read(ROOT / "scripts" / "builderos.py")
    case("five realistic reasoner fixtures map to executable controls", not fixture_problems(fixture_value, runtime_text))
    changed_fixtures = json.loads(json.dumps(fixture_value))
    changed_fixtures["fixtures"][0]["runtime_test"] = "nonexistent optimistic test"
    case("fixture without an executable control is rejected", bool(fixture_problems(changed_fixtures, runtime_text)))

    missing = detect("claude", contract, which=lambda _name: None)
    case("missing Claude CLI is blocked", not selectable(missing) and missing["classification"] == "blocked")

    class Result:
        returncode = 0
        stdout = "2.1.128 (Claude Code)\n"
        stderr = ""

    detected = detect(
        "claude", contract,
        which=lambda _name: Path("C:/fixture/claude.exe"),
        runner=lambda *_args, **_kwargs: Result(),
    )
    case(
        "detected Claude CLI remains execution-unverified",
        selectable(detected)
        and detected["classification"] == "reasonably-assumed"
        and "unverified" in detected["execution"],
    )
    case("legacy state defaults to Codex", selected({})["id"] == "codex")

    switch = continuity_record(
        "reasoner-switch", "R-S3", "S3", "codex", "claude",
        "User explicitly selected Claude.", "verified", "2026-08-23T00:00:00+05:30",
    )
    parent = {"packet_id": "R-S3", "stage": "S3"}
    temporary = ROOT / "validation" / "reasoner-continuity-self-test.json"
    try:
        temporary.write_text(json.dumps(switch, indent=2) + "\n", encoding="utf-8")
        case("reasoner switch evidence passes (positive control)", not continuity_problems(temporary, parent))
        changed_switch = dict(switch)
        changed_switch["gate_effect"] = "G1 approved"
        temporary.write_text(json.dumps(changed_switch, indent=2) + "\n", encoding="utf-8")
        case("reasoner evidence cannot grant a gate", bool(continuity_problems(temporary, parent)))
        changed_switch = dict(switch)
        changed_switch["packet_id"] = "other"
        temporary.write_text(json.dumps(changed_switch, indent=2) + "\n", encoding="utf-8")
        case("wrong reasoner parent is rejected", bool(continuity_problems(temporary, parent)))
    finally:
        if temporary.exists():
            temporary.unlink()

    print("BUILDER OS REASONER SELF-TEST\n")
    for name, passed in cases:
        print(("ok    " if passed else "FAIL  ") + name)
    failed = [name for name, passed in cases if not passed]
    print(f"\n{'FAILED' if failed else 'PASS'}  {len(cases) - len(failed)}/{len(cases)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(self_test())
