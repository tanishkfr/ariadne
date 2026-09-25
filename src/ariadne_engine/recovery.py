"""Explicit, operator-invoked recovery for known interruption states (AR-202 T7).

Recovery here never guesses and never fabricates success:

* detection only *reports* divergences (the AR-201 rule, kept);
* a proposal names the action, the evidence, the authorization it needs and the
  rollback behaviour;
* applying an action either goes through the authoritative transition boundary
  (``statemachine.apply_transition`` for an adopted packet, the execution state
  machine for an abandoned execution) or is a recorded file move (quarantine);
* the pre-recovery state is preserved byte-for-byte so the action is reversible;
* anything the engine cannot distinguish safely is refused and escalated.

The safe actions are deliberately few. An orphan packet is adopted only when it
verifiably belongs to the current boundary (its parent is the recorded tip, its
stage is a legal next stage and the same preconditions that govern any other
transition hold *now*). A missing packet is refused: nothing can reconstruct it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Mapping

from . import contracts, execution as execution_module, persistence, statemachine
from .contracts import ContractError, TransitionRequest

QUARANTINE_DIR = "recovery-quarantine"


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _manifest(packet: Path) -> dict:
    path = Path(packet) / "manifest.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def detect(run_root: Path, state: dict | None = None) -> dict:
    """Report every divergence the engine can see. Read-only."""
    run_root = Path(run_root)
    report = persistence.recovery_report(run_root)
    if state is None:
        try:
            state = persistence.load_state(run_root)
        except Exception:
            state = {}
    findings = list(report.get("findings") or [])
    packets = state.get("packets") or []
    tip = packets[-1] if packets else {}
    tip_id = str(tip.get("id", "")) if isinstance(tip, Mapping) else ""

    for finding in list(findings):
        if finding.get("kind") != "orphan-packet":
            continue
        packet = Path(str(finding.get("path", "")))
        manifest = _manifest(packet)
        parent_id = str(manifest.get("parent_id", ""))
        stage = str(manifest.get("stage", ""))
        finding["expected_parent"] = tip_id
        finding["manifest_parent"] = parent_id
        finding["manifest_stage"] = stage
        finding["belongs_to_tip"] = bool(parent_id) and parent_id == tip_id
        current = statemachine.current_stage(state) if state else None
        finding["legal_next_stage"] = (current, stage or None) in statemachine.STAGE_TRANSITIONS

    for record in execution_module.executions(state):
        if str(record.get("state", "")) in execution_module.TERMINAL_EXECUTION_STATES:
            continue
        task_id = str(record.get("task_id", ""))
        if task_id and task_id == tip_id:
            # The boundary is still current: this execution is in flight, not a
            # divergence. Reporting it would make every active run look broken.
            continue
        findings.append({
            "kind": "interrupted-execution",
            "execution": str(record.get("execution_id", "")),
            "role": str(record.get("role", "")),
            "task_id": task_id,
            "state": str(record.get("state", "")),
            "effect": (
                "the execution never recorded a result and the recorded boundary has moved on; "
                "nothing is inferred about what it produced"
            ),
        })
    completed = [item for item in execution_module.executions(state)
                 if str(item.get("state")) == "COMPLETED"]
    seen: dict[tuple, str] = {}
    for record in completed:
        key = (str(record.get("role", "")), str(record.get("task_id", "")))
        if key in seen:
            findings.append({
                "kind": "duplicate-result",
                "execution": str(record.get("execution_id", "")),
                "first_execution": seen[key],
                "task_id": key[1],
                "effect": "two executions claim a completed result for the same task; state is ambiguous",
            })
        else:
            seen[key] = str(record.get("execution_id", ""))

    for entry in packets:
        if not isinstance(entry, Mapping):
            continue
        path = Path(str(entry.get("path", "")))
        expected = str(entry.get("id", ""))
        manifest = _manifest(path)
        if manifest and expected and str(manifest.get("packet_id", "")) != expected:
            findings.append({
                "kind": "packet-identity-mismatch",
                "packet": expected,
                "path": str(path),
                "manifest_packet_id": str(manifest.get("packet_id", "")),
                "effect": "the recorded packet does not match the manifest on disk; escalate",
            })

    return {
        **report,
        "status": "clean" if not findings else "diverged",
        "findings": findings,
    }


def proposal(finding: Mapping, state: dict | None = None) -> dict:
    """The safe action for one finding, or an explicit refusal."""
    kind = str(finding.get("kind", ""))
    if kind == "interrupted-write":
        return {
            "action": "clear-interrupted-write",
            "target": str(finding.get("path", "")),
            "safe": True,
            "reason": "the live state is intact; the leftover temporary file is not state",
            "requires": ["operator identity", "reason"],
            "rollback": "the quarantined temporary file is preserved and can be moved back",
        }
    if kind == "orphan-packet":
        if not finding.get("belongs_to_tip"):
            return {
                "action": "",
                "target": str(finding.get("packet", "")),
                "safe": False,
                "reason": (
                    "the orphan packet's recorded parent is not the current tip; it may belong to an "
                    "abandoned attempt and adopting it would record a transition that never happened"
                ),
                "requires": ["human inspection"],
                "rollback": "none (nothing is changed)",
            }
        if not finding.get("legal_next_stage"):
            return {
                "action": "",
                "target": str(finding.get("packet", "")),
                "safe": False,
                "reason": "the orphan packet's stage is not a legal transition from the current stage",
                "requires": ["human inspection"],
                "rollback": "none (nothing is changed)",
            }
        return {
            "action": "adopt-packet",
            "target": str(finding.get("packet", "")),
            "safe": True,
            "reason": (
                "the packet's parent is the recorded tip and its stage is a legal next stage; the "
                "transition is re-checked against policy before it is applied"
            ),
            "requires": ["operator identity", "reason", "transition preconditions re-checked"],
            "rollback": "the pre-recovery state is preserved as a byte-identical backup",
        }
    if kind == "missing-packet":
        return {
            "action": "",
            "target": str(finding.get("packet", "")),
            "safe": False,
            "reason": "a packet that is not on disk cannot be reconstructed; nothing is inferred",
            "requires": ["human inspection"],
            "rollback": "none (nothing is changed)",
        }
    if kind == "interrupted-execution":
        record = execution_module.execution(state or {}, str(finding.get("execution", "")))
        if record is None:
            return {
                "action": "",
                "target": str(finding.get("execution", "")),
                "safe": False,
                "reason": "the finding names an execution record that is not in the run state",
                "requires": ["human inspection"],
                "rollback": "none (nothing is changed)",
            }
        return {
            "action": "abandon-execution",
            "target": str(finding.get("execution", "")),
            "safe": True,
            "reason": (
                "the execution is open and the boundary has moved on; recording it as failed with class "
                "INTERRUPTED is truthful and does not claim any result"
            ),
            "requires": ["operator identity", "reason"],
            "rollback": "the pre-recovery state is preserved as a byte-identical backup",
        }
    if kind in ("duplicate-result", "packet-identity-mismatch"):
        return {
            "action": "",
            "target": str(finding.get("execution") or finding.get("packet") or ""),
            "safe": False,
            "reason": "the state is ambiguous; recovery must not choose one result over another",
            "requires": ["human inspection"],
            "rollback": "none (nothing is changed)",
        }
    return {
        "action": "",
        "target": str(finding.get("path") or finding.get("packet") or ""),
        "safe": False,
        "reason": f"no recovery action is defined for {kind or 'an unknown finding'}",
        "requires": ["human inspection"],
        "rollback": "none (nothing is changed)",
    }


def propose(run_root: Path, state: dict, *, target: str = "", action: str = "") -> dict:
    """Return the proposals for the current divergences (optionally one target)."""
    report = detect(run_root, state)
    proposals = []
    for finding in report.get("findings", []):
        item = proposal(finding, state)
        if target and str(item.get("target", "")) != target and str(finding.get("packet", "")) != target:
            continue
        if action:
            # A requested action selects the findings it could apply to, including
            # the ones it must refuse. Filtering out an unsafe finding would answer
            # "nothing here" instead of the refusal reason the operator needs.
            matches = str(item.get("action", "")) == action or (
                action in contracts.RECOVERY_ACTIONS
                and _finding_kind(action) == str(finding.get("kind", ""))
            )
            if not matches:
                continue
        proposals.append({**item, "finding": finding.get("kind")})
    return {"status": report.get("status"), "proposals": proposals}


def _backup(run_root: Path, run_state: dict) -> Path:
    """Preserve the exact pre-recovery bytes. Never overwrite an earlier backup."""
    stamp = contracts.utc_now().replace("-", "").replace(":", "")
    destination = Path(run_root) / f"ariadne-run.recovery-{stamp}.bak"
    counter = 1
    while destination.exists():
        destination = Path(run_root) / f"ariadne-run.recovery-{stamp}-{counter}.bak"
        counter += 1
    destination.write_bytes(persistence.state_path(Path(run_root)).read_bytes())
    return destination


def apply(
    run_root: Path,
    state: dict,
    *,
    action: str,
    target: str,
    identity: str,
    reason: str,
    project: Path | None = None,
    packet_entry: Mapping | None = None,
    policy=None,
) -> tuple[dict, dict]:
    """Apply one safe recovery action. Returns ``(state, recovery_record)``.

    The caller persists ``state`` afterwards. A refusal raises ``PolicyRefusal``
    or ``ContractError`` and changes nothing.
    """
    run_root = Path(run_root)
    if action not in contracts.RECOVERY_ACTIONS:
        raise ContractError(f"unsupported recovery action: {action or 'missing'}")
    if not str(identity or "").strip():
        raise ContractError("recovery needs a recorded operator identity; nothing was changed")
    if not str(reason or "").strip():
        raise ContractError("recovery needs a recorded reason; nothing was changed")

    record = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "recovery_id": contracts.new_record_id("rcv"),
        "action": action,
        "target": str(target),
        "identity": str(identity).strip(),
        "reason": str(reason).strip(),
        "outcome": "refused",
        "evidence": [],
        "backup": "",
        "before": "",
        "after": "",
        "recorded_at": contracts.utc_now(),
    }

    report = detect(run_root, state)
    findings = [item for item in report.get("findings", []) if str(item.get("kind", "")) == _finding_kind(action)]
    if not findings:
        raise ContractError(f"no {_finding_kind(action)} finding matches this recovery request")
    finding = next(
        (
            item for item in findings
            if str(item.get("packet", "")) == str(target) or str(item.get("path", "")) == str(target)
            or str(item.get("execution", "")) == str(target)
        ),
        None,
    )
    if finding is None:
        raise ContractError(f"recovery target {target!r} does not match a current finding")
    safe = proposal(finding, state)
    if not safe.get("safe") or str(safe.get("action", "")) != action:
        raise ContractError(f"recovery refused: {safe.get('reason')}")

    if action == "clear-interrupted-write":
        source = Path(str(finding.get("path", "")))
        if not source.is_file():
            raise ContractError("the temporary file is already gone; nothing was changed")
        record["evidence"].append(f"temporary file sha256 {_sha256(source)}")
        record["before"] = str(source)
        destination = _quarantine(run_root, source)
        shutil.move(str(source), str(destination))
        record["after"] = str(destination)
    elif action == "discard-packet":
        source = Path(str(finding.get("path", "")))
        if not source.is_dir():
            raise ContractError("the orphan packet directory is already gone; nothing was changed")
        record["before"] = str(source)
        manifest_path = source / "manifest.json"
        manifest_digest = _sha256(manifest_path) if manifest_path.is_file() else "missing"
        destination = _quarantine(run_root, source, name=str(finding.get("packet", source.name)))
        shutil.move(str(source), str(destination))
        record["after"] = str(destination)
        record["evidence"].append(f"packet manifest sha256 {manifest_digest}")
    elif action == "adopt-packet":
        if not isinstance(packet_entry, Mapping) or not packet_entry.get("id"):
            raise ContractError("adopting a packet requires the packet entry the runtime would have recorded")
        stage = str(finding.get("manifest_stage", ""))
        if policy is None:
            raise ContractError("adopting a packet requires the policy module so preconditions are re-checked")
        problems = policy.continuation_problems(state, stage, project=Path(project or state.get("project", "")))
        if problems:
            raise ContractError(
                "recovery refused: the recorded preconditions do not hold now: " + "; ".join(problems)
            )
        record["backup"] = str(_backup(run_root, state))
        record["before"] = str(state.get("packets")[-1].get("id", "")) if state.get("packets") else ""
        statemachine.apply_transition(
            state,
            TransitionRequest(
                kind="stage",
                to=stage,
                reason=record["reason"],
                evidence=(str(finding.get("path", "")), str(finding.get("packet", ""))),
                packet=dict(packet_entry),
                actor=record["identity"],
                operation="recovery:adopt-packet",
            ),
            permitted=True,
        )
        record["after"] = str(finding.get("packet", ""))
        record["evidence"].append(
            f"adopted packet {finding.get('packet')} whose parent {finding.get('manifest_parent')} "
            "matches the recorded tip"
        )
    elif action == "abandon-execution":
        execution_id = str(finding.get("execution", ""))
        record["backup"] = str(_backup(run_root, state))
        target_record = execution_module.execution(state, execution_id)
        if target_record is None:
            raise ContractError("the execution record is gone; nothing was changed")
        record["before"] = str(target_record.get("state", ""))
        _record_value, failure = execution_module.abandon(
            state,
            execution_id,
            source="interrupted",
            evidence=[record["recovery_id"], f"execution {execution_id}"],
            detail="an operator recorded that this open execution will not produce a result",
        )
        record["after"] = "FAILED"
        record["evidence"].append(f"failure {failure['failure_id']} class {failure['class']} recorded")
    record["outcome"] = "applied"
    problems = contracts.recovery_problems(record)
    if problems:
        raise ContractError("recovery record would be malformed: " + "; ".join(problems))
    state.setdefault("recoveries", []).append(record)
    return state, record


def _finding_kind(action: str) -> str:
    return {
        "clear-interrupted-write": "interrupted-write",
        "discard-packet": "orphan-packet",
        "adopt-packet": "orphan-packet",
        "abandon-execution": "interrupted-execution",
    }[action]


def _quarantine(run_root: Path, source: Path, *, name: str = "") -> Path:
    root = Path(run_root) / QUARANTINE_DIR
    root.mkdir(parents=True, exist_ok=True)
    stamp = contracts.utc_now().replace("-", "").replace(":", "")
    destination = root / f"{stamp}-{name or source.name}"
    counter = 1
    while destination.exists():
        destination = root / f"{stamp}-{counter}-{name or source.name}"
        counter += 1
    return destination


__all__ = [
    "QUARANTINE_DIR",
    "detect",
    "proposal",
    "propose",
    "apply",
]
