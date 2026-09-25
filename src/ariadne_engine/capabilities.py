"""The live capability registry (AR-203 T2).

AR-202 routing consumed *declared* adapter capabilities. AR-203 keeps that
declaration and adds the evidence around it:

* ``DECLARED``    an adapter says it supports a capability; nothing was checked
* ``DISCOVERED``  the surface was found to exist (a method, an executable on PATH)
* ``AVAILABLE``   a deterministic probe established it can be used here
* ``EXERCISED``   it produced a result in an engine-created execution or a
                  recorded probe artifact the engine re-hashes
* ``VERIFIED``    an existing verification record reproduced the exercised result
* ``UNAVAILABLE`` it cannot be used here, with a recorded reason
* ``UNKNOWN``     nothing established it

The registry never infers a capability from a model or vendor name, never turns a
declaration into a verification, and never makes a paid call to turn a status
green. A capability whose observation no longer matches the surface it was taken
on is ``STALE`` and does not satisfy a strict requirement.

Routing consumes this registry through :func:`capability_status` and
:func:`routing_view`; the policy that decides how much evidence a task needs is
``route_evidence``'s ``evidence_policy`` parameter, and it is explicit.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from . import contracts
from .contracts import (
    CAPABILITY_FAMILIES,
    CAPABILITY_STATUSES,
    CAPABILITY_STATUS_ORDER,
    ContractError,
)

DEFAULT_PROBE_TIMEOUT = 30


def records(state: Mapping) -> list[dict]:
    values = state.get("capability_records")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, Mapping)]


def observations(state: Mapping, *, capability_id: str = "", adapter: str = "", family: str = "") -> list[dict]:
    rows = records(state)
    if capability_id:
        rows = [row for row in rows if str(row.get("capability_id", "")) == str(capability_id)]
    if adapter:
        rows = [row for row in rows if str(row.get("adapter", "")) == str(adapter)]
    if family:
        rows = [row for row in rows if str(row.get("family", "")) == str(family)]
    return rows


def latest(state: Mapping, *, capability_id: str, adapter: str = "", family: str = "") -> dict | None:
    rows = observations(state, capability_id=capability_id, adapter=adapter, family=family)
    return rows[-1] if rows else None


def _digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evidence_rows(evidence: Sequence[Mapping | str]) -> list[dict]:
    rows: list[dict] = []
    for item in evidence or ():
        if isinstance(item, Mapping):
            row = {str(key): value for key, value in item.items()}
        else:
            row = {"detail": str(item)}
        rows.append(row)
    return rows


def _evidence_problems(rows: Sequence[Mapping]) -> list[str]:
    problems: list[str] = []
    for row in rows:
        path_value = str(row.get("path", "") or "")
        digest = str(row.get("sha256", "") or "")
        if not path_value and not digest:
            continue
        if path_value and not Path(path_value).is_file():
            problems.append(f"capability evidence artifact does not exist: {path_value}")
            continue
        if path_value and digest:
            if _digest_file(Path(path_value)) != digest:
                problems.append(f"capability evidence artifact changed after observation: {path_value}")
        elif digest and not path_value:
            problems.append("capability evidence records a digest without an artifact path")
    return problems


def _append(state: dict, record: dict) -> dict:
    contracts.require_collection_capacity(state, "capability_records")
    state.setdefault("capability_records", []).append(record)
    return record


def _supersede(state: dict, *, capability_id: str, adapter: str, family: str, keep: dict) -> None:
    for row in observations(state, capability_id=capability_id, adapter=adapter, family=family):
        if row is keep:
            continue
        if str(row.get("freshness", "")) == "CURRENT" and str(row.get("status", "")) != "SUPERSEDED":
            row["freshness"] = "SUPERSEDED"


def _base_record(
    *,
    capability_id: str,
    adapter: str,
    family: str,
    status: str,
    mechanism: str,
    reason: str,
    evidence: Sequence[Mapping],
    fingerprint: str,
    version: str,
    provider: str,
    model: str,
    runtime: str,
    execution: str,
    verification_id: str,
    observed_by: str,
) -> dict:
    return {
        "schema_version": contracts.SCHEMA_CAPABILITY,
        "capability_record_id": contracts.new_record_id("cap"),
        "run_id": "",
        "capability_id": str(capability_id),
        "adapter": str(adapter),
        "family": str(family),
        "status": str(status),
        "mechanism": str(mechanism),
        "reason": str(reason),
        "evidence": list(evidence),
        "freshness": "CURRENT",
        "surface_fingerprint": str(fingerprint),
        "version": str(version),
        "provider": str(provider),
        "model": str(model),
        "runtime": str(runtime),
        "execution": str(execution),
        "verification_id": str(verification_id),
        "observed_by": str(observed_by),
        "recorded_at": contracts.utc_now(),
    }


def declare(
    state: dict,
    *,
    capability_id: str,
    adapter: str,
    family: str,
    available: bool = True,
    reason: str = "",
    version: str = "",
    provider: str = "",
    model: str = "",
    runtime: str = "",
    fingerprint: str = "",
) -> dict:
    """Record a declaration. A declaration is never more than ``DECLARED``."""
    if family not in CAPABILITY_FAMILIES:
        raise ContractError(f"unsupported capability family: {family!r}")
    if not str(capability_id or "").strip() or not str(adapter or "").strip():
        raise ContractError("a capability declaration needs the capability id and the adapter that declares it")
    status = "DECLARED" if available else "UNAVAILABLE"
    if not available and not str(reason or "").strip():
        raise ContractError("an unavailable capability declaration must record the reason")
    record = _base_record(
        capability_id=capability_id, adapter=adapter, family=family, status=status,
        mechanism="adapter-declaration", reason=reason,
        evidence=[{"detail": "the adapter declares this capability; nothing was checked"}],
        fingerprint=fingerprint, version=version, provider=provider, model=model, runtime=runtime,
        execution="", verification_id="", observed_by="adapter-declaration",
    )
    problems = contracts.capability_record_problems(record)
    if problems:
        raise ContractError("capability declaration is malformed: " + "; ".join(problems))
    _supersede(state, capability_id=capability_id, adapter=adapter, family=family, keep=record)
    return _append(state, record)


def observe(
    state: dict,
    *,
    capability_id: str,
    adapter: str,
    family: str,
    status: str,
    mechanism: str,
    reason: str = "",
    evidence: Sequence[Mapping | str] = (),
    execution: str = "",
    verification_id: str = "",
    fingerprint: str = "",
    version: str = "",
    provider: str = "",
    model: str = "",
    runtime: str = "",
    observed_by: str = "engine-probe",
) -> dict:
    """Record an observed capability fact. Higher statuses carry real obligations."""
    if family not in CAPABILITY_FAMILIES:
        raise ContractError(f"unsupported capability family: {family!r}")
    if status not in CAPABILITY_STATUSES:
        raise ContractError(f"unsupported capability status: {status!r}")
    if status == "DECLARED":
        raise ContractError("use declare() for a declaration; observe() records what was established")
    if not str(mechanism or "").strip():
        raise ContractError("a capability observation must record the mechanism that established it")
    rows = _evidence_rows(evidence)
    problems = _evidence_problems(rows)
    if problems:
        raise ContractError("capability observation is not established: " + "; ".join(problems))
    if CAPABILITY_STATUS_ORDER.get(status, 0) >= CAPABILITY_STATUS_ORDER["AVAILABLE"] and not rows:
        raise ContractError(f"a capability that is {status} must carry the evidence that established it")
    if status == "UNAVAILABLE" and not str(reason or "").strip():
        raise ContractError("an unavailable capability must record the reason it is unavailable")
    if status == "EXERCISED":
        if execution:
            from . import provenance

            provenance.require_engine_execution(state, execution, label="an exercised capability")
        elif str(mechanism).startswith("probe:") and any(
            str(row.get("path", "") or "") or str(row.get("output_sha256", "") or "") for row in rows
        ):
            pass
        else:
            raise ContractError(
                "an exercised capability must name the engine execution or a recorded probe artifact "
                "that produced a result; a claim alone does not exercise anything"
            )
    if status == "VERIFIED":
        from . import verification as verification_module

        record_value = verification_module.verification(state, str(verification_id)) if verification_id else None
        if record_value is None:
            raise ContractError(
                "a verified capability must cite an existing verification record; a declaration or an "
                "exercise alone is not a verification"
            )
        level = str(record_value.get("level", ""))
        if contracts.VERIFICATION_LEVEL_ORDER.get(level, 0) < contracts.VERIFICATION_LEVEL_ORDER["REPRODUCED"]:
            raise ContractError(
                f"verification {verification_id} is only {level}; a capability cannot be VERIFIED from "
                "an observation that was never reproduced"
            )
        if str(record_value.get("freshness", "")) != "CURRENT":
            raise ContractError(
                f"verification {verification_id} is {record_value.get('freshness')}; stale verification "
                "does not satisfy a current capability requirement"
            )
    if CAPABILITY_STATUS_ORDER.get(status, 0) >= CAPABILITY_STATUS_ORDER["AVAILABLE"] and not (
        str(mechanism).startswith("probe:")
        or str(mechanism) in ("engine-execution", "engine-verification")
    ):
        raise ContractError(
            f"a capability that is {status} must be established by a deterministic probe or an engine "
            f"execution, not by {str(mechanism)!r}; a claim alone does not establish a capability"
        )
    record = _base_record(
        capability_id=capability_id, adapter=adapter, family=family, status=status,
        mechanism=mechanism, reason=reason, evidence=rows, fingerprint=fingerprint,
        version=version, provider=provider, model=model, runtime=runtime,
        execution=execution, verification_id=verification_id, observed_by=observed_by,
    )
    record["run_id"] = str(state.get("run_id", ""))
    problems = contracts.capability_record_problems(record)
    if problems:
        raise ContractError("capability observation is malformed: " + "; ".join(problems))
    _supersede(state, capability_id=capability_id, adapter=adapter, family=family, keep=record)
    return _append(state, record)


def capability_status(
    state: Mapping,
    *,
    family: str,
    adapter: str,
    capability_id: str,
    declared: Sequence[str] = (),
) -> dict:
    """The resolved registry status for one adapter capability.

    Without a registry record the answer is ``DECLARED`` when the adapter itself
    declares the capability and ``UNKNOWN`` otherwise. It is never ``UNAVAILABLE``
    without evidence, and never ``VERIFIED`` from a declaration.
    """
    record = latest(state, capability_id=capability_id, adapter=adapter, family=family)
    if record is None:
        if capability_id in set(str(item) for item in declared):
            return {
                "status": "DECLARED",
                "freshness": "UNKNOWN",
                "reason": "the adapter declares this capability; no registry observation exists",
                "record": None,
            }
        return {
            "status": "UNKNOWN",
            "freshness": "UNKNOWN",
            "reason": "no declaration and no observation establish this capability",
            "record": None,
        }
    freshness = str(record.get("freshness", "UNKNOWN"))
    status = str(record.get("status", "UNKNOWN"))
    if freshness == "SUPERSEDED":
        status = "UNKNOWN"
    elif freshness == "STALE":
        status = "UNKNOWN"
    return {
        "status": status,
        "freshness": freshness,
        "reason": str(record.get("reason", "")),
        "record": dict(record),
    }


def routing_view(state: Mapping, adapters: Mapping, *, family: str) -> dict:
    """Per-adapter capability status for routing, from declaration plus registry."""
    view: dict[str, dict] = {}
    for adapter_id, adapter in dict(adapters or {}).items():
        declared = [str(item) for item in adapter.capabilities()]
        view[str(adapter_id)] = {
            capability: capability_status(
                state, family=family, adapter=str(adapter_id), capability_id=capability, declared=declared,
            )
            for capability in declared
        }
    return view


def satisfies(status: str, freshness: str, *, policy: str) -> tuple[bool, str]:
    """Whether a capability evidence level satisfies a routing evidence policy.

    ``declared``  the historical behaviour: a declared capability is enough; an
                  observed ``UNAVAILABLE`` still blocks, and an observed
                  ``EXERCISED``/``VERIFIED`` is recorded as stronger
    ``observed``  requires at least ``AVAILABLE`` with a known freshness
    ``strict``    requires ``EXERCISED`` or ``VERIFIED`` and ``CURRENT`` freshness

    A policy that cannot be satisfied produces a reason the route records, never
    a silent downgrade.
    """
    if policy not in ("declared", "observed", "strict"):
        raise ContractError(f"unknown capability evidence policy: {policy!r}")
    order = CAPABILITY_STATUS_ORDER.get(status, 0)
    if status == "UNAVAILABLE":
        return False, "the capability was observed unavailable here"
    if status == "UNKNOWN":
        return False, "no evidence establishes this capability (UNKNOWN)"
    if policy == "declared":
        return True, ""
    if policy == "observed":
        if order >= CAPABILITY_STATUS_ORDER["AVAILABLE"] and freshness in ("CURRENT", "UNKNOWN"):
            return True, ""
        return False, f"policy 'observed' requires at least AVAILABLE, not {status} ({freshness})"
    if order >= CAPABILITY_STATUS_ORDER["EXERCISED"] and freshness == "CURRENT":
        return True, ""
    return False, f"policy 'strict' requires EXERCISED or VERIFIED with CURRENT freshness, not {status} ({freshness})"


# ------------------------------------------------------------------- probes

@dataclass(frozen=True)
class ProbeResult:
    """What one deterministic probe established. Never a paid or external call."""

    status: str
    reason: str = ""
    evidence: tuple[dict, ...] = ()
    fingerprint: str = ""
    version: str = ""
    mechanism: str = "probe"


class CapabilityProbe:
    """A deterministic, offline check of one capability surface."""

    id = "abstract-probe"
    family = "tool"
    capability_id = "abstract"
    adapter = "abstract"

    def describe(self) -> dict:
        return {
            "probe": self.id,
            "family": self.family,
            "capability_id": self.capability_id,
            "adapter": self.adapter,
            "mechanism": self.mechanism(),
        }

    def mechanism(self) -> str:
        return "probe"

    def surface_fingerprint(self) -> str:
        return ""

    def run(self) -> ProbeResult:
        raise ContractError(f"probe {self.id!r} implements nothing")


class ExecutableProbe(CapabilityProbe):
    """Whether a named executable exists on PATH. No process is started."""

    def __init__(self, command: str, *, capability_id: str = "", adapter: str = "", family: str = "tool") -> None:
        self.command = str(command)
        self.capability_id = capability_id or str(command)
        self.adapter = adapter or f"executable:{command}"
        self.family = family

    def mechanism(self) -> str:
        return "probe:executable-exists"

    def surface_fingerprint(self) -> str:
        resolved = shutil.which(self.command) or ""
        return hashlib.sha256(f"executable|{self.command}|{resolved}".encode("utf-8")).hexdigest()

    def run(self) -> ProbeResult:
        resolved = shutil.which(self.command)
        if not resolved:
            return ProbeResult(
                status="UNAVAILABLE",
                reason=f"executable {self.command!r} is not on PATH",
                evidence=({"detail": f"shutil.which({self.command!r}) returned nothing"},),
                fingerprint=self.surface_fingerprint(),
                mechanism=self.mechanism(),
            )
        return ProbeResult(
            status="AVAILABLE",
            reason="",
            evidence=({"detail": f"executable resolved to {resolved}"},),
            fingerprint=self.surface_fingerprint(),
            mechanism=self.mechanism(),
        )


class AdapterMethodProbe(CapabilityProbe):
    """Whether an adapter object declares a capability and implements the method."""

    METHOD_BY_CAPABILITY = {
        "discover": "discover",
        "retrieve_metadata": "retrieve_metadata",
        "retrieve_content": "retrieve_content",
        "inspect_visual": "inspect_visual",
        "inspect_interaction": "inspect_interaction",
        "screenshot": "capture",
        "interaction": "capture",
        "accessibility": "capture",
        "console": "capture",
        "dom": "capture",
        "measurement": "capture",
        "video": "capture",
        "browser": "capture",
    }

    def __init__(self, adapter, capability_id: str, *, family: str = "reference") -> None:
        self.adapter = adapter
        self.capability_id = str(capability_id)
        self.family = family
        self.adapter_id = str(getattr(adapter, "id", adapter.__class__.__name__))

    def mechanism(self) -> str:
        return "probe:adapter-method"

    def surface_fingerprint(self) -> str:
        method = self.METHOD_BY_CAPABILITY.get(self.capability_id, "")
        present = bool(method) and callable(getattr(self.adapter, method, None))
        return hashlib.sha256(
            f"adapter|{self.adapter_id}|{self.adapter.__class__.__name__}|{self.capability_id}|{present}".encode("utf-8")
        ).hexdigest()

    def run(self) -> ProbeResult:
        declared = [str(item) for item in self.adapter.capabilities()]
        if self.capability_id not in declared:
            return ProbeResult(
                status="UNAVAILABLE",
                reason=f"adapter {self.adapter_id!r} does not declare {self.capability_id!r}",
                evidence=({"detail": "the adapter's own capabilities() does not list it"},),
                fingerprint=self.surface_fingerprint(),
                mechanism=self.mechanism(),
            )
        method_name = self.METHOD_BY_CAPABILITY.get(self.capability_id, "")
        if not method_name:
            return ProbeResult(
                status="DISCOVERED",
                reason="the capability is declared but has no probeable method mapping",
                evidence=({"detail": f"no method mapping exists for {self.capability_id!r}"},),
                fingerprint=self.surface_fingerprint(),
                mechanism=self.mechanism(),
            )
        method = getattr(self.adapter, method_name, None)
        if not callable(method):
            return ProbeResult(
                status="UNAVAILABLE",
                reason=f"adapter {self.adapter_id!r} declares {self.capability_id!r} but has no callable {method_name}()",
                evidence=({"detail": f"{self.adapter_id}.{method_name} is not callable"},),
                fingerprint=self.surface_fingerprint(),
                mechanism=self.mechanism(),
            )
        return ProbeResult(
            status="AVAILABLE",
            reason="",
            evidence=({"detail": f"{self.adapter_id}.{method_name}() exists and the adapter declares the capability"},),
            fingerprint=self.surface_fingerprint(),
            mechanism=self.mechanism(),
        )


class FixtureCommandProbe(CapabilityProbe):
    """Run one declared command inside an isolated fixture and record the result.

    This is the ``EXERCISED`` probe: the command really runs (no shell, no
    network assumptions, a bounded timeout) and its stdout digest is recorded as
    evidence. It is used only for commands the operator declares; nothing here
    installs or fetches anything.
    """

    def __init__(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        capability_id: str,
        adapter: str = "",
        family: str = "tool",
        timeout: int = DEFAULT_PROBE_TIMEOUT,
        expect_returncode: int = 0,
    ) -> None:
        if not argv:
            raise ContractError("a fixture command probe needs an argv")
        self.argv = [str(item) for item in argv]
        self.cwd = Path(cwd)
        self.capability_id = str(capability_id)
        self.adapter = adapter or "fixture:" + " ".join(self.argv[:2])
        self.family = family
        self.timeout = int(timeout)
        self.expect_returncode = int(expect_returncode)

    def mechanism(self) -> str:
        return "probe:fixture-command"

    def surface_fingerprint(self) -> str:
        resolved = shutil.which(self.argv[0]) or ""
        return hashlib.sha256(f"fixture|{self.argv[0]}|{resolved}|{' '.join(self.argv[1:])}".encode("utf-8")).hexdigest()

    def run(self) -> ProbeResult:
        self.cwd.mkdir(parents=True, exist_ok=True)
        if not self.cwd.is_dir():
            return ProbeResult(
                status="UNAVAILABLE", reason=f"probe fixture directory is not usable: {self.cwd}",
                evidence=({"detail": "the declared fixture directory does not exist"},),
                fingerprint=self.surface_fingerprint(), mechanism=self.mechanism(),
            )
        try:
            completed = subprocess.run(
                self.argv, cwd=str(self.cwd), capture_output=True, text=True,
                timeout=self.timeout, shell=False,
            )
        except FileNotFoundError:
            return ProbeResult(
                status="UNAVAILABLE", reason=f"probe command {self.argv[0]!r} was not found",
                evidence=({"detail": "the command could not be started"},),
                fingerprint=self.surface_fingerprint(), mechanism=self.mechanism(),
            )
        except subprocess.TimeoutExpired:
            return ProbeResult(
                status="UNAVAILABLE", reason=f"probe command timed out after {self.timeout}s",
                evidence=({"detail": "the command did not finish inside the bounded timeout"},),
                fingerprint=self.surface_fingerprint(), mechanism=self.mechanism(),
            )
        output = (completed.stdout or "") + (completed.stderr or "")
        digest = hashlib.sha256(output.encode("utf-8", errors="replace")).hexdigest()
        if completed.returncode != self.expect_returncode:
            return ProbeResult(
                status="UNAVAILABLE",
                reason=f"probe command exited {completed.returncode}, expected {self.expect_returncode}",
                evidence=({"detail": "the command ran but did not produce the expected result", "output_sha256": digest},),
                fingerprint=self.surface_fingerprint(), mechanism=self.mechanism(),
            )
        return ProbeResult(
            status="EXERCISED",
            reason="",
            evidence=(
                {"detail": "the declared command ran to the expected exit code in an isolated fixture",
                 "output_sha256": digest, "argv": list(self.argv)},
            ),
            fingerprint=self.surface_fingerprint(),
            version=str(completed.stdout or "").strip().splitlines()[0][:120] if (completed.stdout or "").strip() else "",
            mechanism=self.mechanism(),
        )


def run_probe(state: dict, probe: CapabilityProbe, *, reason: str = "") -> dict:
    """Run one deterministic probe and record its observation. Never fabricates."""
    result = probe.run()
    status = result.status
    record = observe(
        state,
        capability_id=probe.capability_id,
        adapter=probe.adapter,
        family=probe.family,
        status=status,
        mechanism=result.mechanism or probe.mechanism(),
        reason=reason or result.reason,
        evidence=list(result.evidence),
        fingerprint=result.fingerprint or probe.surface_fingerprint(),
        version=result.version,
        observed_by="engine-probe",
    )
    return {
        "probe": probe.describe(),
        "status": status,
        "reason": record.get("reason", ""),
        "record": record,
    }


def summarise(state: Mapping) -> dict:
    """Deterministic capability-registry counters."""
    rows = records(state)
    counts = {status.lower(): 0 for status in CAPABILITY_STATUSES}
    for row in rows:
        counts[str(row.get("status", "")).lower()] = counts.get(str(row.get("status", "")).lower(), 0) + 1
    families: dict[str, int] = {}
    for row in rows:
        key = str(row.get("family", "unknown"))
        families[key] = families.get(key, 0) + 1
    return {
        "records": len(rows),
        "statuses": counts,
        "families": dict(sorted(families.items())),
        "stale": sum(1 for row in rows if str(row.get("freshness")) == "STALE"),
        "unavailable": counts.get("unavailable", 0),
    }


def describe(record: Mapping) -> str:
    return (
        f"{record.get('capability_id')} on {record.get('adapter')}: {record.get('status')} "
        f"({record.get('mechanism')}, {record.get('freshness')})"
    )


__all__ = [
    "DEFAULT_PROBE_TIMEOUT",
    "records",
    "observations",
    "latest",
    "declare",
    "observe",
    "capability_status",
    "routing_view",
    "satisfies",
    "ProbeResult",
    "CapabilityProbe",
    "ExecutableProbe",
    "AdapterMethodProbe",
    "FixtureCommandProbe",
    "run_probe",
    "summarise",
    "describe",
]
