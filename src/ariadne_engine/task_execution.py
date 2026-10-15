"""Task execution: worker adapters, preflight, task records, and skill evidence (Ariadne 2.3B).

Phase 2.3A could interpret a request and prepare a bounded T1 worker packet. This
module is the orchestration layer that turns that packet into a completed,
validated, reviewed and verified task *without inventing a new engine*:

* **Worker adapters** are declared execution capabilities of the host environment
  (a CLI coding harness, the invoking assistant session, or a human-driven
  session). An adapter declares what it can do; nothing is inferred from a model
  or vendor name, and a CLI adapter's availability is a discovered executable,
  never an assumption. Preset adapters describe the documented host integrations;
  only a real execution promotes an adapter beyond ``DECLARED``/``AVAILABLE``.
* **Selection and preflight** choose an adapter for one task from measured facts:
  required capabilities, declared adapter capabilities, discovered executables,
  recorded failures for the task, and the declared preference order. An
  unsatisfiable requirement produces an honest blocker that names every
  adapter's status, never a fabricated run.
* **Task records** give each T1 task its own durable identity inside one run:
  objective, scope, contract hash, baseline revision, attempts, returns,
  validation, review, proof and acceptance. A second task attaches to the same
  run without a second authoritative history.
* **Skill evidence** records which selected methods were actually invoked and
  which completed with engine-observable evidence. Selection alone is not
  execution: a skill is ``completed`` only when the engine observed the evidence
  its registry entry expects, and a mandatory method the worker did not report
  is recorded as ``unmet`` rather than silently credited.

The module is deliberately free of runtime imports: the runtime
(``scripts/ariadne.py``) owns packet transport, execution identities, state
persistence and the CLI, and calls into here for the orchestration decisions.
Everything in this module is a pure function of the records it is given.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Mapping, Sequence

from . import contracts
from .contracts import ContractError

EXECUTION_POLICY = "task-execution-1"

METHODS_HEADING = "Methods applied"
"""The T1 return section that reports which selected methods ran, and how."""

# --------------------------------------------------------------- adapter model

CLI_HARNESS = "cli-harness"
HOST_SESSION = "host-session"
MANUAL = "manual"
ADAPTER_KINDS = (CLI_HARNESS, HOST_SESSION, MANUAL)

WORKER_ADAPTER_CAPABILITIES = (
    "read", "search", "edit", "shell",
    "implementation", "implementation-repair", "escalation",
)
"""What a worker adapter may declare it can do.

``implementation`` is the ability to carry out a bounded change in a repository;
``implementation-repair`` the ability to act on a prior failed validation;
``escalation`` the ability to take over from a weaker worker. A capability that
is absent is absent; the selector never assumes one.
"""


def _adapter(
    adapter_id: str,
    *,
    title: str,
    kind: str,
    command: str = "",
    argv: tuple[str, ...] = (),
    capabilities: tuple[str, ...] = (),
    preference: int = 0,
    note: str = "",
    prompt_mode: str = "stdin",
) -> dict:
    return {
        "id": adapter_id,
        "title": title,
        "kind": kind,
        "command": str(command),
        "argv": tuple(str(item) for item in argv),
        "capabilities": tuple(str(item) for item in capabilities),
        "preference": int(preference),
        "note": str(note),
        "prompt_mode": str(prompt_mode),
    }


WORKER_ADAPTERS: dict[str, dict] = {
    "host-session": _adapter(
        "host-session",
        title="Invoking assistant session",
        kind=HOST_SESSION,
        capabilities=("read", "search", "edit", "shell", "implementation", "implementation-repair", "escalation"),
        preference=0,
        note=(
            "the assistant that invoked Ariadne performs the packet in its own session and "
            "records its return through the runtime; availability is the caller's declaration"
        ),
    ),
    "claude-code": _adapter(
        "claude-code",
        title="Claude Code CLI",
        kind=CLI_HARNESS,
        command="claude",
        argv=("--print", "--permission-mode", "acceptEdits", "--allowedTools", "Read,Edit,Write,Bash,Glob,Grep"),
        capabilities=("read", "search", "edit", "shell", "implementation", "implementation-repair", "escalation"),
        preference=1,
        note="headless invocation of the installed Claude Code CLI; no credentials are read or stored",
    ),
    "codex": _adapter(
        "codex",
        title="Codex CLI",
        kind=CLI_HARNESS,
        command="codex",
        argv=("exec", "--full-auto", "-"),
        capabilities=("read", "search", "edit", "shell", "implementation", "implementation-repair", "escalation"),
        preference=2,
        note="headless invocation of the installed Codex CLI",
    ),
    "cursor": _adapter(
        "cursor",
        title="Cursor agent CLI",
        kind=CLI_HARNESS,
        command="cursor-agent",
        argv=("--print", "--force"),
        capabilities=("read", "search", "edit", "shell", "implementation", "implementation-repair", "escalation"),
        preference=3,
        note="headless invocation of the installed Cursor agent CLI",
    ),
    "opencode": _adapter(
        "opencode",
        title="OpenCode CLI",
        kind=CLI_HARNESS,
        command="opencode",
        argv=("run",),
        capabilities=("read", "search", "edit", "shell", "implementation", "implementation-repair", "escalation"),
        preference=4,
        note="headless invocation of the installed OpenCode CLI",
    ),
    "manual": _adapter(
        "manual",
        title="Human-driven external session",
        kind=MANUAL,
        capabilities=("implementation", "implementation-repair"),
        preference=9,
        note=(
            "a person performs the packet in an external tool and records the return through "
            "the runtime; the engine never claims to have observed the work itself"
        ),
    ),
}
"""Preset worker adapters.

``preference`` is the lightest-first order used when the caller does not name an
adapter: the invoking session carries no launch cost, then installed CLI
harnesses, then a human-driven session. The order is a policy input, not a
measurement; per-task cost stays ``UNKNOWN`` unless a harness reports usage.
"""


def adapter_registry(extra: Mapping | None = None) -> dict[str, dict]:
    registry = {key: dict(value) for key, value in WORKER_ADAPTERS.items()}
    for adapter_id, value in dict(extra or {}).items():
        registry[str(adapter_id)] = dict(value)
    return registry


def custom_adapter(adapter_id: str, command_line: str) -> dict:
    """A declared custom CLI harness from an explicit command line.

    This is the generic consumer boundary: any local tool that accepts a prompt
    on stdin and works inside the project can be used without editing Ariadne.
    The declaration is recorded verbatim; the executable probe decides whether it
    exists.
    """
    parts = [item for item in str(command_line or "").replace("\\", "\\\\").split() if item]
    if not parts:
        raise ContractError("a custom worker command needs at least the executable")
    parts = [part.replace("\\\\", "\\") for part in parts]
    return _adapter(
        str(adapter_id),
        title=f"Custom harness: {parts[0]}",
        kind=CLI_HARNESS,
        command=parts[0],
        argv=tuple(parts[1:]),
        capabilities=("read", "search", "edit", "shell", "implementation", "implementation-repair"),
        preference=5,
        note="custom local harness declared by the caller for this run",
    )


def adapter_problems(adapter: Mapping) -> list[str]:
    problems: list[str] = []
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(adapter.get("id", ""))):
        problems.append(f"adapter id is not a stable identifier: {adapter.get('id')!r}")
    if str(adapter.get("kind", "")) not in ADAPTER_KINDS:
        problems.append(f"adapter {adapter.get('id')} declares an unknown kind: {adapter.get('kind')!r}")
    if str(adapter.get("kind")) == CLI_HARNESS and not str(adapter.get("command", "")).strip():
        problems.append(f"adapter {adapter.get('id')} is a CLI harness without a command")
    for capability in tuple(adapter.get("capabilities") or ()):
        if str(capability) not in WORKER_ADAPTER_CAPABILITIES:
            problems.append(
                f"adapter {adapter.get('id')} declares unknown capability {capability!r}"
            )
    return problems


def registry_problems(registry: Mapping | None = None) -> list[str]:
    problems: list[str] = []
    for adapter_id, adapter in sorted(dict(registry or WORKER_ADAPTERS).items()):
        if str(adapter.get("id", "")) != adapter_id:
            problems.append(f"adapter {adapter_id!r} declares a different id")
        problems.extend(adapter_problems(adapter))
    return problems


def adapter_view(adapter: Mapping, *, available: bool, reason: str = "") -> dict:
    return {
        "id": str(adapter.get("id", "")),
        "title": str(adapter.get("title", "")),
        "kind": str(adapter.get("kind", "")),
        "command": str(adapter.get("command", "")),
        "capabilities": [str(item) for item in adapter.get("capabilities") or ()],
        "preference": int(adapter.get("preference", 0)),
        "note": str(adapter.get("note", "")),
        "available": bool(available),
        "reason": str(reason),
    }


def executable_available(command: str) -> tuple[bool, str]:
    """Discover whether a CLI harness exists. No process is started."""
    resolved = shutil.which(str(command)) if str(command or "").strip() else None
    if resolved:
        return True, f"executable resolved to {resolved}"
    return False, f"executable {command!r} is not on PATH"


def availability(adapter: Mapping) -> tuple[bool, str]:
    kind = str(adapter.get("kind", ""))
    if kind == CLI_HARNESS:
        return executable_available(str(adapter.get("command", "")))
    if kind == HOST_SESSION:
        return True, (
            "the invoking session declared it will perform the packet itself; "
            "no executable probe applies"
        )
    return True, (
        "a human-driven session is declared possible; the engine observes nothing "
        "until a return is recorded"
    )


def select_adapter(
    *,
    required: Sequence[str] = (),
    requested: str = "",
    prior_failures: Sequence[Mapping] = (),
    escalate: bool = False,
    registry: Mapping | None = None,
) -> dict:
    """Choose a worker adapter from declared capabilities and discovered facts.

    Order of decision, each recorded with its reason:

    1. an explicitly requested adapter wins when it is capable and its surface
       exists;
    2. otherwise adapters are considered lightest-first; an adapter whose
       recorded failure for this task already requires a strategy change is
       excluded by name rather than silently retried;
    3. an adapter that cannot declare a required capability is excluded with the
       missing capability named.
    """
    adapters = registry if registry is not None else WORKER_ADAPTERS
    required_ids = [str(item) for item in required if str(item)]
    failure_strategies = {
        str(item.get("strategy", "")).strip()
        for item in prior_failures
        if str(item.get("class", "")) in ("IMPLEMENTATION_FAILURE", "PROVIDER_FAILURE", "TIMEOUT")
        and str(item.get("strategy", "")).strip()
    }
    record = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "selection_id": contracts.new_record_id("wsl"),
        "policy": EXECUTION_POLICY,
        "requested": str(requested),
        "required_capabilities": sorted(set(required_ids)),
        "escalate": bool(escalate),
        "candidates": [],
        "exclusions": [],
        "chosen": {},
        "fallbacks": [],
        "status": "no-adapter",
        "reason": "",
        "recorded_at": contracts.utc_now(),
    }
    ordered = sorted(adapters.values(), key=lambda item: (int(item.get("preference", 0)), str(item.get("id"))))
    if requested:
        if requested not in adapters:
            record["reason"] = f"the requested worker adapter {requested!r} is not a declared adapter"
            return record
        ordered = [adapters[requested]]
    capable: list[tuple[dict, str]] = []
    for adapter in ordered:
        adapter_id = str(adapter.get("id", ""))
        reasons: list[str] = []
        problems = adapter_problems(adapter)
        reasons.extend(problems)
        missing = sorted(set(required_ids) - set(str(item) for item in adapter.get("capabilities") or ()))
        if missing:
            reasons.append("missing required capability: " + ", ".join(missing))
        ok, availability_reason = availability(adapter)
        if not ok:
            reasons.append(availability_reason)
        if adapter_id in failure_strategies and not escalate:
            reasons.append(
                "a recorded failure for this task names this adapter as the strategy that failed"
            )
        row = adapter_view(adapter, available=ok, reason=availability_reason)
        row["exclusions"] = reasons
        record["candidates"].append({
            "id": adapter_id,
            "kind": row["kind"],
            "available": row["available"],
            "capabilities": row["capabilities"],
            "exclusions": reasons,
        })
        if reasons:
            record["exclusions"].append({"id": adapter_id, "reasons": reasons})
        else:
            capable.append((adapter, availability_reason))
    if not capable:
        record["reason"] = (
            "no worker adapter satisfies this task: "
            + "; ".join(
                f"{item['id']} ({'; '.join(item['exclusions'])})" for item in record["candidates"]
            )
            if record["candidates"] else "no worker adapters are declared"
        )
        return record
    chosen, availability_reason = capable[0]
    record["status"] = "selected"
    record["chosen"] = {
        **adapter_view(chosen, available=True, reason=availability_reason),
        "capability_verdict": "sufficient",
    }
    record["fallbacks"] = [
        adapter_view(adapter, available=True, reason=reason)
        for adapter, reason in capable[1:]
    ]
    record["reason"] = (
        f"{chosen.get('id')!r} selected: it declares {', '.join(str(item) for item in chosen.get('capabilities') or ())} "
        f"and its surface exists ({availability_reason})"
        if str(chosen.get("kind")) == CLI_HARNESS else
        f"{chosen.get('id')!r} selected: it declares the required capabilities ({availability_reason})"
    )
    return record


def preflight_required_capabilities(characterisation: Mapping | None) -> list[str]:
    """The capabilities one task genuinely requires, from its characterisation."""
    values = []
    for item in (characterisation or {}).get("required_capabilities") or ():
        if isinstance(item, Mapping) and str(item.get("id", "")).strip():
            values.append(str(item["id"]))
    if not values:
        values = ["implementation"]
    return sorted(set(values))


# ------------------------------------------------------------------ task records

TASK_SCHEMA = "task-execution-1"

TASK_STATES = (
    "prepared",
    "worker-running",
    "repair-pending",
    "returned",
    "validated",
    "render-pending",
    "review-pending",
    "review-failed",
    "verified",
    "accepted",
    "rejected",
    "blocked",
    "escalation-required",
)
"""Derived task states. They are computed from records, never stored as claims."""


def task_records(state: Mapping) -> list[dict]:
    value = state.get("tasks")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def rendered_required(plan: Mapping) -> bool:
    """Whether the plan requires rendered (browser) acceptance evidence."""
    return bool((plan.get("rendered_acceptance") or {}).get("required"))


def _rendered_seed(plan: Mapping) -> dict:
    """The task's rendered-acceptance ledger, seeded from the plan."""
    declared = dict((plan.get("rendered_acceptance") or {}))
    return {
        "required": bool(declared.get("required")),
        "interaction": bool(declared.get("interaction")),
        "reasons": [str(item) for item in declared.get("reasons") or ()],
        "capture_capability": dict(declared.get("capture_capability") or {}),
        "evidence_sets": [],
        "blocked_reason": "",
        "status": "required" if declared.get("required") else "not-required",
    }


def record_rendered(
    task: dict,
    *,
    status: str,
    packet_id: str = "",
    evidence_set_id: str = "",
    capture_ids: Sequence[str] = (),
    evidence_ids: Sequence[str] = (),
    revision_hash: str = "",
    render_source_digest: str = "",
    manifest_path: str = "",
    blocked_reason: str = "",
) -> dict:
    """Record one attempt at the task's rendered acceptance.

    Only the engine writes this: it is what makes "the UI task was rendered and
    seen" checkable from records instead of from a sentence in a return. A
    capture that could not run is recorded as ``blocked`` with its reason, never
    as a pass. The record names the packet whose revision it tried to render, so
    a later repair can tell whether the failure describes the attempt it is
    repairing.
    """
    rendered = task.setdefault("rendered", _rendered_seed({}))
    rendered["status"] = str(status)
    rendered["blocked_reason"] = str(blocked_reason)
    rendered["packet_id"] = str(packet_id or rendered.get("packet_id", ""))
    rendered["recorded_at"] = contracts.utc_now()
    if evidence_set_id:
        row = {
            "evidence_set_id": str(evidence_set_id),
            "capture_ids": [str(item) for item in capture_ids],
            "evidence_ids": [str(item) for item in evidence_ids],
            "revision_hash": str(revision_hash),
            "render_source_digest": str(render_source_digest),
            "manifest_path": str(manifest_path),
            "recorded_at": contracts.utc_now(),
        }
        rendered.setdefault("evidence_sets", []).append(row)
    task["updated_at"] = contracts.utc_now()
    return rendered


def rendered_satisfied(task: Mapping, *, revision_hash: str = "", source_digest: str = "") -> bool:
    """Whether a passed evidence set exists for this task at the given identity.

    A set recorded against a different revision does not satisfy the current one:
    rendered evidence is bound to the implementation bytes it captured, and a
    later repair invalidates it exactly like a stale validation. ``source_digest``
    checks the ``render_source_digest`` recorded at capture time against the
    implementation as it is now, which catches an edit made after the capture
    even when no new packet exists.
    """
    rendered = dict(task.get("rendered") or {})
    if not rendered.get("required"):
        return True
    if str(rendered.get("status")) != "captured":
        return False
    rows = [
        row for row in rendered.get("evidence_sets") or ()
        if isinstance(row, Mapping)
    ]
    if revision_hash:
        rows = [row for row in rows if str(row.get("revision_hash", "")) == str(revision_hash)]
    if source_digest:
        rows = [row for row in rows if str(row.get("render_source_digest", "")) == str(source_digest)]
    return bool(rows)


def current_task(state: Mapping) -> dict | None:
    rows = task_records(state)
    return rows[-1] if rows else None


def find_task(state: Mapping, task_id: str) -> dict | None:
    for row in reversed(task_records(state)):
        if str(row.get("task_id", "")) == str(task_id):
            return row
    return None


def find_task_for_packet(state: Mapping, packet_id: str) -> dict | None:
    """The task record one packet belongs to: its own id, or a linked attempt.

    Repair attempts carry their own packet ids and belong to the task whose
    chain they extend; this is how a retry packet is attributed without a second
    task record.
    """
    direct = find_task(state, packet_id)
    if direct is not None:
        return direct
    for row in reversed(task_records(state)):
        for attempt in row.get("attempts") or ():
            if str(attempt.get("packet_id", "")) == str(packet_id):
                return row
    return None


def create_task(
    state: dict,
    *,
    plan: Mapping,
    task_id: str,
    packet_id: str,
    packet_path: str,
    baseline: Mapping | None,
    contract_sha256: str,
    attempt: int = 1,
    attach: Mapping | None = None,
) -> dict:
    """Create one durable task record and append it to the run state."""
    frame = dict(plan.get("frame") or {})
    scope_view = plan.get("scope") or {}
    validation_view = plan.get("validation") or {}
    selection = dict(plan.get("skills") or {})
    record = {
        "schema_version": TASK_SCHEMA,
        "task_id": str(task_id),
        "plan_id": str(plan.get("plan_id", "")),
        "policy": EXECUTION_POLICY,
        "objective": str(plan.get("request", "")).strip(),
        "intent": str(frame.get("family", "")),
        "intent_confidence": str(frame.get("confidence", "")),
        "workflow": str((plan.get("workflow") or {}).get("family", "")),
        "execution_path": str((plan.get("path") or {}).get("path", "")),
        "write_authorization": str(plan.get("write_authorization", "")),
        "scope": {
            "declared": [str(item) for item in scope_view.get("declared") or ()],
            "protected": [dict(item) for item in scope_view.get("protected") or () if isinstance(item, Mapping)],
        },
        "validation": {
            "declared": [str(item) for item in validation_view.get("declared") or ()],
        },
        "contract_sha256": str(contract_sha256),
        "skills": [
            {
                "id": str(item.get("id", "")),
                "title": str(item.get("title", "")),
                "mandatory": bool(item.get("mandatory")),
                "state": "selected",
                "mechanism": "selection",
                "evidence": [],
                "recorded_at": contracts.utc_now(),
            }
            for item in selection.get("selected") or ()
        ],
        "attempts": [],
        "review": {},
        "rendered": _rendered_seed(plan),
        "proof": {},
        "acceptance": {},
        "attach": dict(attach or {}),
        "baseline": {
            "head": str((baseline or {}).get("head", "")),
            "state": str((baseline or {}).get("state", "")),
            "recorded_at": contracts.utc_now(),
        },
        "created_at": contracts.utc_now(),
        "updated_at": contracts.utc_now(),
        "policy_version": contracts.POLICY_VERSION,
    }
    problems = task_problems(record)
    if problems:
        raise ContractError("task record is malformed: " + "; ".join(problems))
    contracts.require_collection_capacity(state, "tasks")
    state.setdefault("tasks", []).append(record)
    return record


def task_problems(record: Mapping) -> list[str]:
    problems: list[str] = []
    if not isinstance(record, Mapping):
        return ["task record is not an object"]
    if str(record.get("schema_version", "")) != TASK_SCHEMA:
        problems.append("task record has an unsupported schema version")
    for name in ("task_id", "plan_id", "objective", "policy", "created_at"):
        if not str(record.get(name, "")).strip():
            problems.append(f"task record has no {name}")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", str(record.get("task_id", ""))):
        problems.append("task record has a malformed task id")
    if not isinstance(record.get("attempts"), list):
        problems.append("task record has no attempt list")
    for skill in record.get("skills") or ():
        if not isinstance(skill, Mapping) or not str(skill.get("id", "")).strip():
            problems.append("task record has a malformed skill ledger entry")
            break
        if str(skill.get("state", "")) not in ("selected", "invoked", "completed", "unmet"):
            problems.append(f"skill ledger entry {skill.get('id')} has an unsupported state")
            break
    rendered = record.get("rendered")
    if rendered is not None:
        if not isinstance(rendered, Mapping):
            problems.append("task record rendered ledger is not an object")
        elif str(rendered.get("status", "")) not in ("not-required", "required", "captured", "blocked"):
            problems.append(f"task rendered ledger has an unsupported status: {rendered.get('status')!r}")
    return problems


def attempt_for(task: Mapping | None, packet_id: str) -> dict | None:
    for attempt in (task or {}).get("attempts") or ():
        if str(attempt.get("packet_id", "")) == str(packet_id):
            return attempt
    return None


def open_attempt(task: Mapping | None) -> dict | None:
    """The attempt that has started and not yet settled."""
    terminal = ("validated", "failed", "blocked")
    for attempt in reversed((task or {}).get("attempts") or ()):
        if str(attempt.get("outcome", "")) not in terminal:
            return attempt
    return None


def prepare_attempt(task: dict, *, packet_id: str, packet_path: str, attempt: int = 1) -> dict:
    """Record a prepared attempt when its packet is prepared.

    The attempt exists from preparation on, so the lifecycle can never be
    confused with a worker that started without a bounded contract, and a status
    check sees "prepared, not yet run" instead of nothing.
    """
    existing = attempt_for(task, packet_id)
    if existing is not None:
        raise ContractError(f"an attempt record for packet {packet_id!r} already exists")
    row = {
        "packet_id": str(packet_id),
        "packet_path": str(packet_path),
        "attempt": int(attempt),
        "adapter": "",
        "execution_id": "",
        "state": "prepared",
        "outcome": "open",
        "prepared_at": contracts.utc_now(),
        "baseline": {},
        "return": {},
        "validation": {},
    }
    task.setdefault("attempts", []).append(row)
    task["updated_at"] = contracts.utc_now()
    return row


def start_attempt(
    task: dict,
    *,
    packet_id: str,
    adapter: str,
    execution_id: str,
    baseline: Mapping | None,
) -> dict:
    """Record a worker actually starting the prepared attempt."""
    attempt = attempt_for(task, packet_id)
    if attempt is None:
        raise ContractError(f"no prepared attempt exists for packet {packet_id!r}; a run cannot adopt a packet")
    attempt["state"] = "running"
    attempt["adapter"] = str(adapter)
    attempt["execution_id"] = str(execution_id)
    attempt["started_at"] = contracts.utc_now()
    attempt["baseline"] = {
        "head": str((baseline or {}).get("head", "")),
        "state": str((baseline or {}).get("state", "")),
    }
    task["updated_at"] = contracts.utc_now()
    return attempt


def record_attempt_return(
    task: dict,
    *,
    packet_id: str,
    status: str,
    return_path: str,
    machine_path: str,
    metadata: Mapping,
    methods: Sequence[Mapping],
    execution_id: str,
) -> dict:
    attempt = attempt_for(task, packet_id)
    if attempt is None:
        raise ContractError(f"no attempt record exists for packet {packet_id!r}; a return cannot be adopted")
    attempt["state"] = "returned"
    attempt["return"] = {
        "status": str(status),
        "path": str(return_path),
        "machine": str(machine_path),
        "metadata": {str(key): str(value) for key, value in dict(metadata).items()},
        "methods": [dict(item) for item in methods],
        "execution_id": str(execution_id),
        "recorded_at": contracts.utc_now(),
    }
    task["updated_at"] = contracts.utc_now()
    return attempt


def record_attempt_validation(
    task: dict,
    *,
    packet_id: str,
    status: str,
    failure_kind: str,
    failure_reason: str,
    validation_path: str,
    scope_status: str,
    commands: Sequence[Mapping] = (),
    skills: Sequence[Mapping] = (),
    retryable: bool = False,
) -> dict:
    attempt = attempt_for(task, packet_id)
    if attempt is None:
        raise ContractError(f"no attempt record exists for packet {packet_id!r}")
    attempt["state"] = "validated" if status == "passed" else "failed"
    attempt["outcome"] = "validated" if status == "passed" else ("blocked" if status == "blocked" else "failed")
    attempt["validation"] = {
        "status": str(status),
        "failure_kind": str(failure_kind),
        "failure_reason": str(failure_reason),
        "path": str(validation_path),
        "scope_status": str(scope_status),
        "retryable": bool(retryable),
        "commands": [dict(item) for item in commands],
        "skills": [dict(item) for item in skills],
        "recorded_at": contracts.utc_now(),
    }
    task["updated_at"] = contracts.utc_now()
    return attempt


def record_review(task: dict, *, record: Mapping) -> dict:
    task["review"] = {
        "review_id": str(record.get("review_id", "")),
        "outcome": str(record.get("outcome", "")),
        "recommendation": str(record.get("recommendation", "")),
        "reviewer_identity": str(record.get("reviewer_identity", "")),
        "independence_level": str(record.get("independence_level", "")),
        "findings": [str(item) for item in record.get("findings") or ()],
        "packet_id": str(record.get("packet_id", "")),
        "recorded_at": contracts.utc_now(),
    }
    task["updated_at"] = contracts.utc_now()
    return task["review"]


def record_proof(task: dict, *, receipt: Mapping) -> dict:
    task["proof"] = {
        "proof_id": str(receipt.get("proof_id", "")),
        "acceptance_state": str(receipt.get("acceptance_state", "")),
        "work_digest": str(receipt.get("work_digest", "")),
        "requirements": len(receipt.get("requirements") or ()),
        "recorded_at": contracts.utc_now(),
    }
    task["updated_at"] = contracts.utc_now()
    return task["proof"]


def record_acceptance(task: dict, *, outcome: str, identity: str, reason: str) -> dict:
    if str(outcome) not in ("accepted", "rejected"):
        raise ContractError(f"unsupported acceptance outcome: {outcome!r}")
    if not str(identity or "").strip():
        raise ContractError("a human acceptance decision needs the recorded identity that made it")
    task["acceptance"] = {
        "outcome": str(outcome),
        "identity": str(identity).strip(),
        "reason": str(reason).strip(),
        "recorded_at": contracts.utc_now(),
    }
    task["updated_at"] = contracts.utc_now()
    return task["acceptance"]


def set_task_skill(
    task: dict,
    *,
    skill_id: str,
    state_value: str,
    mechanism: str,
    evidence: Sequence[str] = (),
    note: str = "",
) -> dict:
    if state_value not in ("selected", "invoked", "completed", "unmet"):
        raise ContractError(f"unsupported skill ledger state: {state_value!r}")
    for entry in task.setdefault("skills", []):
        if str(entry.get("id", "")) == str(skill_id):
            # The ledger only strengthens inside one attempt chain; a later
            # attempt may still move a skill forward, never regress a completion
            # that a real observation established.
            if str(entry.get("state")) == "completed" and state_value != "completed":
                return entry
            entry.update({
                "state": str(state_value),
                "mechanism": str(mechanism),
                "evidence": [str(item) for item in evidence],
                "note": str(note),
                "recorded_at": contracts.utc_now(),
            })
            task["updated_at"] = contracts.utc_now()
            return entry
    raise ContractError(f"the task ledger has no selected skill {skill_id!r}")


def skills_missing_from_report(task: Mapping, methods: Sequence[Mapping]) -> list[str]:
    reported = {str(item.get("skill", "")).strip() for item in methods}
    return [
        str(entry.get("id"))
        for entry in (task or {}).get("skills") or ()
        if str(entry.get("id")) not in reported
    ]


# --------------------------------------------------------------- methods report

def parse_methods_section(text: str) -> list[dict]:
    """Parse the ``## Methods applied`` section of a T1 return handoff.

    Each bullet is ``- <skill-id>: <what was actually done and observed>``. The
    parser is deliberately strict about shape and records the evidence verbatim;
    judging it is the caller's job.
    """
    match = re.search(rf"(?im)^##\s+{re.escape(METHODS_HEADING)}\s*$", str(text or ""))
    if not match:
        return []
    remainder = text[match.end():]
    end = re.search(r"(?m)^##\s+\S", remainder)
    section = remainder[: end.start()] if end else remainder
    rows: list[dict] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line.startswith(("-", "*")):
            continue
        body = line.lstrip("-* ").strip()
        if not body or re.search(r"<[^>]+>", body):
            continue
        parts = re.split(r"\s*[:—–]\s*", body, maxsplit=1)
        if len(parts) != 2:
            continue
        skill = re.sub(r"[^a-z0-9-]", "", parts[0].strip().lower())
        evidence = " ".join(parts[1].split())
        if skill and evidence:
            rows.append({"skill": skill, "evidence": evidence})
    return rows


PLACEHOLDER_EVIDENCE = re.compile(r"^(none|n/?a|not used|unrecorded|unknown)\.?$", re.I)


def methods_report_problems(text: str, selected_skill_ids: Sequence[str]) -> list[str]:
    """Whether a T1 return reports every selected method, with usable evidence.

    The section and one entry per selected skill are required: the task contract
    named the methods, so a return that never mentions a method leaves the
    question of whether it ran unanswerable. An entry whose evidence is a bare
    placeholder is refused for the same reason. An entry that states the method
    was not used is accepted *here* (it is honest); the ledger records it as
    ``unmet``, not as completed.
    """
    problems: list[str] = []
    selected = [str(item) for item in selected_skill_ids]
    if not selected:
        return problems
    if not re.search(rf"(?im)^##\s+{re.escape(METHODS_HEADING)}\s*$", str(text or "")):
        problems.append(f"return handoff is missing the {METHODS_HEADING} section the task contract requires")
        return problems
    rows = parse_methods_section(text)
    by_skill: dict[str, list[dict]] = {}
    for row in rows:
        by_skill.setdefault(str(row.get("skill", "")), []).append(row)
    for skill_id in selected:
        entries = by_skill.get(skill_id) or []
        if not entries:
            problems.append(f"return handoff does not report the selected method {skill_id!r}")
            continue
        if len(entries) > 1:
            problems.append(f"return handoff reports the selected method {skill_id!r} more than once")
            continue
        evidence = str(entries[0].get("evidence", ""))
        if PLACEHOLDER_EVIDENCE.match(evidence.strip()):
            problems.append(
                f"return handoff reports method {skill_id!r} without evidence "
                "(say what was done and what happened, or say it was not used and why)"
            )
    return problems


def evaluate_skill_evidence(
    task: Mapping,
    methods: Sequence[Mapping],
    *,
    validation_passed: bool,
    review_outcome: str = "",
) -> list[dict]:
    """The ledger updates one completed validation implies, from observed facts.

    A skill's registry entry names the evidence it produces. Only the outputs the
    engine can actually observe promote a method to ``completed``:

    * ``behavior-tests`` completed when a required validation command ran and passed;
    * ``root-cause`` completed when the worker reported a reproduction *and* the
      independent validation passed on the changed revision;
    * ``adversarial-review`` completed when a recorded independent review exists
      for this task;
    * every other method the worker reported stays ``invoked`` (worker-reported);
      it is never silently promoted to completed, because nothing in this run
      observed its output.

    A selected method the worker did not report is ``unmet`` when it is
    mandatory, and ``selected`` (not executed) otherwise.
    """
    updates: list[dict] = []
    reported = {str(item.get("skill", "")): str(item.get("evidence", "")) for item in methods}
    for entry in (task or {}).get("skills") or ():
        skill_id = str(entry.get("id", ""))
        evidence = reported.get(skill_id)
        if evidence is None:
            state_value = "unmet" if entry.get("mandatory") else "selected"
            note = (
                "selected and mandatory, but the return did not report it"
                if entry.get("mandatory") else
                "selected but not reported by the worker"
            )
            updates.append({
                "skill_id": skill_id, "state": state_value, "mechanism": "engine-observation",
                "evidence": [], "note": note,
            })
            continue
        lowered = evidence.strip().lower()
        if PLACEHOLDER_EVIDENCE.match(lowered):
            updates.append({
                "skill_id": skill_id, "state": "unmet", "mechanism": "worker-reported",
                "evidence": [evidence], "note": "the worker reported the method without usable evidence",
            })
            continue
        if skill_id == "behavior-tests" and validation_passed:
            updates.append({
                "skill_id": skill_id, "state": "completed", "mechanism": "engine-observed",
                "evidence": [evidence, "a required validation command passed on this revision"],
                "note": "the engine reran the required checks the method demands",
            })
            continue
        if skill_id == "root-cause" and validation_passed and re.search(
            r"(?i)\b(reproduc|failing|failure|error|before)\b", evidence
        ):
            updates.append({
                "skill_id": skill_id, "state": "completed", "mechanism": "engine-observed",
                "evidence": [evidence, "the independent validation passed on the reported revision"],
                "note": "the worker reported a reproduction and the revision validates",
            })
            continue
        if skill_id == "adversarial-review" and review_outcome == "passed":
            updates.append({
                "skill_id": skill_id, "state": "completed", "mechanism": "engine-observed",
                "evidence": [evidence, "a recorded independent review exists for this task"],
                "note": "review independence is established by engine executions",
            })
            continue
        updates.append({
            "skill_id": skill_id, "state": "invoked", "mechanism": "worker-reported",
            "evidence": [evidence],
            "note": (
                "reported by the worker; nothing in this run observed the method's own output, "
                "so it is not recorded as completed"
            ),
        })
    return updates


# ----------------------------------------------------------------- resume view

def task_status_value(
    task: Mapping,
    *,
    review_required: bool,
    rendered_required: bool | None = None,
    rendered_satisfied: bool | None = None,
) -> str:
    """The derived state of one task from its records, nothing else.

    ``rendered_required``/``rendered_satisfied`` default to the task's own
    rendered ledger, so callers that only know about review keep working: a UI
    task with a validated attempt and no captures derives ``render-pending``,
    and no caller has to remember to ask.
    """
    rendered = dict(task.get("rendered") or {})
    if rendered_required is None:
        rendered_required = bool(rendered.get("required"))
    if rendered_satisfied is None:
        rendered_satisfied = (
            True if not rendered_required else str(rendered.get("status")) == "captured"
        )
    acceptance = dict(task.get("acceptance") or {})
    if str(acceptance.get("outcome")) == "accepted":
        return "accepted"
    if str(acceptance.get("outcome")) == "rejected":
        return "rejected"
    if task.get("proof"):
        return "verified"
    review = dict(task.get("review") or {})
    if review.get("outcome") == "failed":
        return "review-failed"
    if review.get("outcome") == "passed":
        return "validated"
    attempts = list(task.get("attempts") or ())
    attempts_desc = list(reversed(attempts))
    latest = attempts_desc[0] if attempts_desc else {}
    if not attempts:
        return "prepared"
    if str(latest.get("state")) == "prepared":
        return "prepared"
    if str(latest.get("state")) == "running":
        return "worker-running"
    if str(latest.get("state")) == "returned":
        return "returned"
    if str(latest.get("state")) == "validated":
        if rendered_required and not rendered_satisfied:
            return "render-pending"
        return "review-pending" if review_required else "validated"
    if str(latest.get("state")) == "failed":
        validation = dict(latest.get("validation") or {})
        if str(validation.get("failure_kind")) in (
            "contract", "out-of-scope", "dangerous-action", "repository-conflict", "worker-blocked"
        ):
            return "escalation-required"
        earlier_validated = any(
            str(item.get("outcome")) == "validated" for item in attempts_desc if item is not latest
        )
        if earlier_validated:
            if rendered_required and not rendered_satisfied:
                return "render-pending"
            return "validated"
        return "repair-pending" if validation.get("retryable") else "blocked"
    return "prepared"


def review_is_required(plan: Mapping | None) -> bool:
    path = (plan or {}).get("path") or {}
    retained = {str(item) for item in path.get("retained") or ()}
    return "review" in retained


def continuation_point(task: Mapping, *, review_required: bool) -> str:
    """The one next action for the task, derived from records."""
    status = task_status_value(task, review_required=review_required)
    return {
        "prepared": "run the prepared attempt in a worker adapter (task-run), or perform it in this session and record the return",
        "worker-running": "wait for the worker, or recover the interrupted attempt in the operations log",
        "repair-pending": "prepare the bounded repair attempt (task-repair) from the recorded validation failure",
        "returned": "run Ariadne's independent validation (task-validate) before anything else",
        "validated": "run Ariadne Proof Pass against the original request (task-verify)",
        "render-pending": "capture the required browser-rendered acceptance evidence (task-render) against this revision",
        "review-pending": "obtain the required independent review (task-review) before completion",
        "review-failed": "inspect the review findings and repair within the bounded budget",
        "verified": "the engine is done; the human acceptance decision remains (task-accept)",
        "accepted": "complete: the human accepted the verified result",
        "rejected": "the human rejected the result; repair or abandon deliberately",
        "blocked": "blocked: inspect the recorded failure and escalate or abandon deliberately",
        "escalation-required": "escalate to a stronger worker adapter or a human decision",
    }.get(status, "inspect the recorded task state")


__all__ = [
    "EXECUTION_POLICY",
    "METHODS_HEADING",
    "CLI_HARNESS",
    "HOST_SESSION",
    "MANUAL",
    "ADAPTER_KINDS",
    "WORKER_ADAPTER_CAPABILITIES",
    "WORKER_ADAPTERS",
    "adapter_registry",
    "custom_adapter",
    "adapter_problems",
    "registry_problems",
    "adapter_view",
    "executable_available",
    "availability",
    "select_adapter",
    "preflight_required_capabilities",
    "TASK_SCHEMA",
    "TASK_STATES",
    "task_records",
    "current_task",
    "find_task",
    "find_task_for_packet",
    "create_task",
    "task_problems",
    "rendered_required",
    "record_rendered",
    "rendered_satisfied",
    "attempt_for",
    "open_attempt",
    "prepare_attempt",
    "start_attempt",
    "record_attempt_return",
    "record_attempt_validation",
    "record_review",
    "record_proof",
    "record_acceptance",
    "set_task_skill",
    "skills_missing_from_report",
    "parse_methods_section",
    "methods_report_problems",
    "evaluate_skill_evidence",
    "task_status_value",
    "review_is_required",
    "continuation_point",
]
