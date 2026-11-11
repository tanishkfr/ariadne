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

import json
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
    "command-code": _adapter(
        "command-code",
        title="Command Code CLI",
        kind=CLI_HARNESS,
        command="command-code",
        # Non-interactive print mode; the prompt is read from stdin. The model
        # is the operator's configured Command Code model unless the adapter
        # preset names one. DeepSeek V4.1 Flash is the documented 2.4A default
        # for live qualification, and --no-session keeps the run isolated.
        argv=(
            "-p", "--skip-onboarding", "--trust", "--permission-mode", "accept-edits",
            # Command Code 1.88.5 withholds edit/write tools from headless runs
            # unless they are enabled explicitly; a session that cannot write a
            # file is not a worker. The engine's independent scope check and
            # validation remain the boundary, so enabling the declared
            # capabilities here does not widen what the task may change.
            "--tools-all",
            "--no-session", "--model", "deepseek/deepseek-v4.1-flash",
        ),
        capabilities=("read", "search", "edit", "shell", "implementation", "implementation-repair", "escalation"),
        preference=1,
        note="headless invocation of the installed Command Code CLI; no credentials are read or stored",
    ),
    "claude-code": _adapter(
        "claude-code",
        title="Claude Code CLI",
        kind=CLI_HARNESS,
        command="claude",
        argv=("--print", "--permission-mode", "acceptEdits", "--allowedTools", "Read,Edit,Write,Bash,Glob,Grep"),
        capabilities=("read", "search", "edit", "shell", "implementation", "implementation-repair", "escalation"),
        preference=2,
        note="headless invocation of the installed Claude Code CLI; no credentials are read or stored",
    ),
    "codex": _adapter(
        "codex",
        title="Codex CLI",
        kind=CLI_HARNESS,
        command="codex",
        # Codex CLI 0.160 dropped the historical --full-auto shorthand (and exec
        # never prompts anyway); the explicit sandbox flag is the supported
        # spelling, and a non-interactive exec already answers approval with
        # "never". The prompt is still read from stdin via the trailing dash.
        argv=("exec", "--sandbox", "workspace-write", "--skip-git-repo-check", "-"),
        capabilities=("read", "search", "edit", "shell", "implementation", "implementation-repair", "escalation"),
        preference=3,
        note="headless invocation of the installed Codex CLI",
    ),
    "cursor": _adapter(
        "cursor",
        title="Cursor agent CLI",
        kind=CLI_HARNESS,
        command="cursor-agent",
        argv=("--print", "--force"),
        capabilities=("read", "search", "edit", "shell", "implementation", "implementation-repair", "escalation"),
        preference=4,
        note="headless invocation of the installed Cursor agent CLI",
    ),
    "opencode": _adapter(
        "opencode",
        title="OpenCode CLI",
        kind=CLI_HARNESS,
        command="opencode",
        argv=("run", "--auto"),
        capabilities=("read", "search", "edit", "shell", "implementation", "implementation-repair", "escalation"),
        preference=5,
        note="headless invocation of the installed OpenCode CLI; --auto permits the bounded edit it was given",
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


ADAPTER_CONFORMANCE_CHECKS = (
    "identity",
    "kind-and-transport",
    "capability-declaration",
    "executable-discovery",
    "version-reporting",
    "authentication",
    "argument-compatibility",
    "working-directory",
    "prompt-delivery",
    "file-edit-permission",
    "structured-return",
    "cancellation",
    "timeout",
    "nonzero-exit",
    "interrupted-session-recovery",
    "scope-enforcement",
    "independent-validation",
)
"""The checks every worker adapter is measured against.

``executable-discovery`` is an engine fact. The rest are either structural
(declared by the adapter) or observed in a live qualification run. A check this
environment did not execute is ``not-observed``, never ``pass``: a declaration
is not an integration.
"""


def adapter_conformance(
    adapter: Mapping,
    *,
    environment: Mapping | None = None,
) -> dict:
    """One adapter's conformance report, separating declarations from observations."""
    environment = dict(environment or {})
    problems = adapter_problems(adapter)
    available = False
    discovery_reason = ""
    if str(adapter.get("kind")) == CLI_HARNESS:
        available, discovery_reason = executable_available(str(adapter.get("command", "")))
    else:
        available, discovery_reason = True, "no executable is required for this adapter kind"
    structural = {
        "identity": bool(str(adapter.get("id", "")).strip()),
        "kind-and-transport": str(adapter.get("kind")) in ADAPTER_KINDS,
        "capability-declaration": bool(adapter.get("capabilities")),
        "executable-discovery": available,
    }
    rows: dict[str, dict] = {}
    for check in ADAPTER_CONFORMANCE_CHECKS:
        if check in structural:
            if check == "executable-discovery":
                rows[check] = {
                    "status": "pass" if available else "blocked",
                    "source": "engine-structure",
                    "detail": discovery_reason,
                }
            else:
                rows[check] = {
                    "status": "pass" if structural[check] else "fail",
                    "source": "engine-structure",
                    "detail": "",
                }
            continue
        observed = environment.get(check)
        if isinstance(observed, Mapping):
            rows[check] = {
                "status": str(observed.get("status", "not-observed")),
                "source": str(observed.get("source", "live-observation")),
                "detail": str(observed.get("detail", "")),
            }
        else:
            declared = {
                "version-reporting": bool(str(adapter.get("command", "")).strip()),
                "authentication": str(adapter.get("kind")) != CLI_HARNESS,
                "argument-compatibility": bool(adapter.get("argv") is not None),
                "working-directory": True,
                "prompt-delivery": str(adapter.get("prompt_mode", "stdin")) in ("stdin", "argument"),
                "file-edit-permission": "edit" in tuple(adapter.get("capabilities") or ()),
                "structured-return": True,
                "cancellation": True,
                "timeout": True,
                "nonzero-exit": True,
                "interrupted-session-recovery": True,
                "scope-enforcement": True,
                "independent-validation": True,
            }.get(check, False)
            rows[check] = {
                "status": "declared" if declared else "not-observed",
                "source": "adapter-declaration",
                "detail": "not executed in a live qualification run",
            }
    failed = [name for name, row in rows.items() if row["status"] == "fail"]
    unobserved = [name for name, row in rows.items() if row["status"] in ("declared", "not-observed")]
    return {
        "adapter": str(adapter.get("id", "")),
        "kind": str(adapter.get("kind", "")),
        "available": available,
        "discovery": discovery_reason,
        "problems": problems,
        "checks": rows,
        "failed": failed,
        "unobserved": unobserved,
        "verdict": (
            "fail" if failed or problems else
            "unavailable" if not available else
            "conformant-live" if not unobserved else
            "declared-not-live"
        ),
    }


def conformance_matrix(
    registry: Mapping | None = None,
    *,
    environments: Mapping | None = None,
) -> dict:
    environments = dict(environments or {})
    adapters = dict(registry or WORKER_ADAPTERS)
    rows = [
        adapter_conformance(adapter, environment=environments.get(adapter_id, {}))
        for adapter_id, adapter in sorted(adapters.items())
    ]
    return {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "checks": list(ADAPTER_CONFORMANCE_CHECKS),
        "adapters": rows,
        "declared": len(rows),
        "live": [row["adapter"] for row in rows if row["verdict"] == "conformant-live"],
        "not_live": [row["adapter"] for row in rows if row["verdict"] != "conformant-live"],
    }


def adapter_view(adapter: Mapping, *, available: bool, reason: str = "") -> dict:
    return {
        "id": str(adapter.get("id", "")),
        "title": str(adapter.get("title", "")),
        "kind": str(adapter.get("kind", "")),
        "command": str(adapter.get("command", "")),
        "capabilities": [str(item) for item in adapter.get("capabilities") or ()],
        "preference": int(adapter.get("preference", 0)),
        "note": str(adapter.get("note", "")),
        "prompt_mode": str(adapter.get("prompt_mode", "stdin")),
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
    evidence_ranking: Sequence[str] = (),
    evidence: Mapping | None = None,
) -> dict:
    """Choose a worker adapter from declared capabilities and discovered facts.

    Order of decision, each recorded with its reason:

    1. an explicitly requested adapter wins when it is capable and its surface
       exists;
    2. otherwise adapters are considered lightest-first; an adapter whose
       recorded failure for this task already requires a strategy change is
       excluded by name rather than silently retried;
    3. an adapter that cannot declare a required capability is excluded with the
       missing capability named;
    4. a caller-supplied ``evidence_ranking`` may reorder only the adapters that
       already satisfy 1-3. The ranking is never trusted to add an adapter, drop
       an exclusion, or bypass an explicit request. The caller is responsible
       for the promotion gate; this selector records the evidence block it was
       given and nothing more.
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
        "evidence": dict(evidence or {}),
        "evidence_applied": False,
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
    if evidence_ranking and not requested:
        rank = {str(item): index for index, item in enumerate(evidence_ranking) if str(item).strip()}
        before = [str(item[0].get("id", "")) for item in capable]
        capable = sorted(
            capable,
            key=lambda pair: (
                rank.get(str(pair[0].get("id", "")), len(rank)),
                int(pair[0].get("preference", 0)),
                str(pair[0].get("id", "")),
            ),
        )
        after = [str(item[0].get("id", "")) for item in capable]
        record["evidence_applied"] = bool(rank) and before != after
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
    "stale-evidence",
)
"""Derived task states. They are computed from records, never stored as claims."""

REPAIR_KINDS = ("routine", "review", "rendered", "escalation", "interruption")
"""Why a corrective attempt exists.

``routine`` is a retry after a failed engine validation and spends the bounded
routine-repair budget. ``review`` is a review-directed correction: only a
recorded failed review authorizes it, and it spends its own smaller budget
without inheriting any previous validation. ``rendered`` corrects a capture
failure, ``escalation`` is a deliberate stronger-worker retry, and
``interruption`` continues an attempt whose worker disappeared.
"""

MAX_REVIEW_CORRECTIONS = 2
"""Review-directed corrections permitted inside one task.

Kept separate from ``policy.MAX_ROUTINE_REPAIRS``: a review finding is a
different authorization than a failed validation, and merging the budgets
would let a worker turn repeated failed reviews into unlimited retries.
"""

TASK_OPERATION_KINDS = (
    "launch",
    "execute",
    "collect-return",
    "ingest-return",
    "validate",
    "persist-evidence",
    "review",
    "repair",
    "proof",
    "accept",
)
"""Durable operation phases used for recovery.

Each phase is recorded *before* the side effect it describes. A started
operation without a completed/failed record is an interrupted operation, and
recovery reports it rather than assuming the side effect happened.
"""

TASK_OPERATION_STATES = ("started", "completed", "failed", "interrupted", "refused")
OPERATION_HISTORY_LIMIT = 100


def attempt_id_for(packet_id: str) -> str:
    """The stable identity of one attempt, derived from its packet identity.

    Packet ids are already unique inside a run; this name makes the attempt
    identity explicit in records that need to distinguish "which attempt" from
    "which packet directory". It is deterministic, so a repeated adoption finds
    the same attempt instead of minting a second one.
    """
    return f"atm_{str(packet_id)}"


def latest_attempt(task: Mapping | None) -> dict:
    attempts = (task or {}).get("attempts") or []
    return attempts[-1] if attempts else {}


def attempt_is_latest(task: Mapping | None, attempt: Mapping | None) -> bool:
    if not attempt:
        return False
    return str(attempt.get("packet_id", "")) == str((latest_attempt(task) or {}).get("packet_id", ""))


def review_belongs_to(task: Mapping | None, review: Mapping | None, attempt: Mapping | None) -> bool:
    """Whether a review record is about this exact attempt and revision.

    A review that names another attempt, another packet or another validation
    digest is stale evidence: it cannot approve a revision it never saw.
    """
    review = review or {}
    attempt = attempt or {}
    if not review or not attempt:
        return False
    if str(review.get("task_id", "")) and str(review.get("task_id")) != str((task or {}).get("task_id", "")):
        return False
    if str(review.get("packet_id", "")) != str(attempt.get("packet_id", "")):
        return False
    review_attempt = str(review.get("attempt_id", ""))
    if review_attempt and review_attempt != str(attempt.get("attempt_id", "")):
        return False
    validation = dict(attempt.get("validation") or {})
    expected = str(validation.get("validation_sha256", ""))
    recorded = str(review.get("validation_sha256", ""))
    if expected and recorded and expected != recorded:
        return False
    return True


def validation_belongs_to(attempt: Mapping | None, record: Mapping | None) -> bool:
    """Whether a validation record is bound to the attempt it claims to settle."""
    attempt = attempt or {}
    record = record or {}
    if not record:
        return False
    if str(record.get("packet_id", "")) != str(attempt.get("packet_id", "")):
        return False
    attempt_name = str(record.get("attempt_id", ""))
    if attempt_name and attempt_name != str(attempt.get("attempt_id", "")):
        return False
    execution = dict(record.get("execution") or {})
    implementing = str(execution.get("implementing_execution", ""))
    attempt_execution = str(attempt.get("execution_id", ""))
    if implementing and attempt_execution and implementing != attempt_execution:
        return False
    return True


def proof_is_current(task: Mapping | None) -> bool:
    """A proof receipt only stands for the attempt and revision it was made from."""
    task = task or {}
    proof = dict(task.get("proof") or {})
    if not proof:
        return False
    if proof.get("stale"):
        return False
    attempt = latest_attempt(task)
    if not str(proof.get("packet_id", "")) or not str(proof.get("attempt_id", "")):
        return False
    if str(proof.get("packet_id", "")) and str(proof.get("packet_id")) != str(attempt.get("packet_id", "")):
        return False
    if str(proof.get("attempt_id", "")) and str(proof.get("attempt_id")) != str(attempt.get("attempt_id", "")):
        return False
    validation = dict(attempt.get("validation") or {})
    if str(proof.get("validation_sha256", "")) and str(proof.get("validation_sha256")) != str(
        validation.get("validation_sha256", "")
    ):
        return False
    return True


def review_is_current(task: Mapping | None) -> bool:
    """The current review, if it is about the current attempt and still passing."""
    task = task or {}
    review = dict(task.get("review") or {})
    attempt = latest_attempt(task)
    return bool(review) and review_belongs_to(task, review, attempt)


def review_correction_count(task: Mapping | None) -> int:
    return sum(
        1
        for attempt in (task or {}).get("attempts") or ()
        if str(attempt.get("repair_kind", "")) == "review"
    )


def executor_identities(task: Mapping | None) -> list[str]:
    """Every worker identity this task's attempts have carried, lower-cased.

    Used to refuse a reviewer that is one of the task's own implementers. It is
    a label check on top of the stronger engine-execution check: both must agree
    that review and implementation are separate.
    """
    values: set[str] = set()
    for attempt in (task or {}).get("attempts") or ():
        for key in ("adapter", "execution_id"):
            value = str(((attempt or {}).get(key)) or "").strip().lower()
            if value:
                values.add(value)
        returned = dict((attempt or {}).get("return") or {})
        metadata = dict(returned.get("metadata") or {})
        for key in ("provider", "model", "worker role"):
            value = str(metadata.get(key, "") or "").strip().lower()
            if value:
                values.add(value)
    return sorted(values)


def _scope_digest(scope: Sequence[str] | None) -> str:
    import hashlib
    import json

    values = sorted({str(item).replace("\\", "/") for item in (scope or ()) if str(item)})
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode("utf-8")).hexdigest()


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
        "reviews": [],
        "review": {},
        "operations": [],
        "current_operation": "",
        "current_attempt_id": "",
        "review_corrections": 0,
        "review_correction_limit": MAX_REVIEW_CORRECTIONS,
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
    for attempt in record.get("attempts") or ():
        if not isinstance(attempt, Mapping):
            problems.append("task record has a malformed attempt entry")
            break
        if not str(attempt.get("packet_id", "")).strip():
            problems.append("task attempt has no packet id")
            break
        if str(attempt.get("repair_kind", "")) and str(attempt.get("repair_kind")) not in REPAIR_KINDS:
            problems.append(f"task attempt has an unsupported repair kind: {attempt.get('repair_kind')!r}")
            break
    for item in record.get("operations") or ():
        if not isinstance(item, Mapping) or str(item.get("kind", "")) not in TASK_OPERATION_KINDS:
            problems.append("task record has a malformed operation entry")
            break
        if str(item.get("state", "")) not in TASK_OPERATION_STATES:
            problems.append(f"task operation has an unsupported state: {item.get('state')!r}")
            break
    for item in record.get("reviews") or ():
        if not isinstance(item, Mapping) or not str(item.get("review_id", "")).strip():
            problems.append("task record has a malformed review-history entry")
            break
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


def prepare_attempt(
    task: dict,
    *,
    packet_id: str,
    packet_path: str,
    attempt: int = 1,
    parent_attempt_id: str = "",
    repair_kind: str = "",
    review_id: str = "",
    review_finding: str = "",
    authorized_by: str = "",
    directive: Mapping | None = None,
) -> dict:
    """Record a prepared attempt when its packet is prepared.

    The attempt exists from preparation on, so the lifecycle can never be
    confused with a worker that started without a bounded contract, and a status
    check sees "prepared, not yet run" instead of nothing. A corrective attempt
    records its parent, the review that authorized it and the finding it must
    address; those fields are evidence, never a new authorization channel. A
    fresh attempt always starts with an empty validation record: no correction
    can inherit a prior pass.
    """
    existing = attempt_for(task, packet_id)
    if existing is not None:
        raise ContractError(f"an attempt record for packet {packet_id!r} already exists")
    if repair_kind and repair_kind not in REPAIR_KINDS:
        raise ContractError(f"unsupported repair kind: {repair_kind!r}")
    scope = [str(item) for item in (task.get("scope") or {}).get("declared") or ()]
    row = {
        "attempt_id": attempt_id_for(packet_id),
        "packet_id": str(packet_id),
        "packet_path": str(packet_path),
        "attempt": int(attempt),
        "parent_attempt_id": str(parent_attempt_id),
        "repair_kind": str(repair_kind),
        "review_id": str(review_id),
        "review_finding": str(review_finding),
        "authorized_by": str(authorized_by),
        "directive": dict(directive or {}),
        "scope_digest": _scope_digest(scope),
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
    task["current_attempt_id"] = str(row["attempt_id"])
    task["updated_at"] = contracts.utc_now()
    return row


def attempt_scope_problems(task: Mapping, attempt: Mapping) -> list[str]:
    """A correction may not widen the authorized scope it inherited.

    The scope is the task's declared scope; both the task record and the parent
    attempt carry a digest of it. A changed digest means the plan or task record
    moved under the correction and the attempt cannot be trusted to stay inside
    the authorization that was granted for the original work.
    """
    problems: list[str] = []
    declared = [str(item) for item in ((task or {}).get("scope") or {}).get("declared") or ()]
    if not declared:
        return problems
    expected = _scope_digest(declared)
    parent_digest = str((attempt or {}).get("scope_digest", ""))
    if parent_digest and parent_digest != expected:
        problems.append(
            "the task's declared scope changed after the parent attempt; a correction cannot widen or "
            "replace the authorized scope"
        )
    return problems


def corrective_attempt_problems(
    task: Mapping,
    attempt: Mapping,
    *,
    repair_kind: str,
) -> list[str]:
    """Whether a correction is authorized by the records that exist.

    Routine repair is authorized by a retryable failed validation. A review
    correction is authorized *only* by a recorded failed review of the current
    attempt with the ``fix and re-review`` recommendation. A passing attempt with
    no such finding needs no rerun and is refused here rather than wasting a
    worker attempt.
    """
    problems: list[str] = []
    task = task or {}
    attempt = attempt or {}
    if not attempt_is_latest(task, attempt):
        problems.append("a correction must continue from the latest attempt, not an older one")
    problems.extend(attempt_scope_problems(task, attempt))
    if str((task.get("acceptance") or {}).get("outcome", "")) in ("accepted", "rejected"):
        problems.append("the task already records a human decision; prepare a new deliberate task instead")
    review = dict(task.get("review") or {})
    if repair_kind == "review":
        if str(review.get("outcome", "")) != "failed":
            problems.append("a review-directed correction needs a recorded failed review for the current attempt")
        elif not review_belongs_to(task, review, attempt):
            problems.append(
                "the recorded review is not bound to the current attempt and validation; it cannot authorize a correction"
            )
        if str(review.get("recommendation", "")).lower() != "fix and re-review":
            problems.append(
                "the review recommendation does not authorize a correction "
                "(only 'fix and re-review' does; 'present g3' needs acceptance and 'restart the direction' needs a new direction)"
            )
        if review_correction_count(task) >= int(task.get("review_correction_limit", MAX_REVIEW_CORRECTIONS) or 0):
            problems.append(
                "the review-directed correction budget is exhausted; a further pass needs a human decision"
            )
    elif repair_kind in ("routine", "interruption"):
        validation = dict(attempt.get("validation") or {})
        if not validation.get("retryable"):
            problems.append("a routine correction needs a retryable failed validation on the current attempt")
    return problems


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
    validated_revision: Mapping | None = None,
) -> dict:
    """Record one engine validation against exactly one attempt.

    ``status == "passed"`` is refused unless a real validation record exists on
    disk and it is bound to this attempt's packet and implementing execution. A
    worker failure (no validation record) can only be failed or blocked: there is
    no path from an incomplete validation to a pass. The record's digest is
    stored beside the attempt so a later review can prove which validation it
    reviewed and a stale one can be refused by name.
    """
    attempt = attempt_for(task, packet_id)
    if attempt is None:
        raise ContractError(f"no attempt record exists for packet {packet_id!r}")
    if str(status) not in ("passed", "failed", "blocked"):
        raise ContractError(f"unsupported attempt validation status: {status!r}")
    if str(validation_path or "").strip() and Path(str(validation_path)).is_file():
        try:
            recorded = json.loads(Path(str(validation_path)).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContractError(f"the attempt validation record is unreadable: {exc}") from exc
        if isinstance(recorded, dict):
            recorded = {**recorded, "attempt_id": str(recorded.get("attempt_id", attempt.get("attempt_id", "")))}
            if not validation_belongs_to(attempt, recorded):
                raise ContractError(
                    "the validation record is not bound to this attempt's packet or implementing execution; "
                    "a correction cannot inherit another attempt's evidence"
                )
    if str(status) == "passed":
        path = Path(str(validation_path or ""))
        if not str(validation_path or "").strip() or not path.is_file():
            raise ContractError("a passed attempt validation needs its durable validation record on disk")
        attempt_dir = Path(str(attempt.get("packet_path", ""))).resolve()
        try:
            path.resolve().relative_to(attempt_dir)
        except (ValueError, OSError):
            raise ContractError(
                "the validation record is outside this attempt's own packet; cross-attempt evidence cannot settle it"
            )
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContractError(f"the passed validation record is unreadable: {exc}") from exc
        if not isinstance(value, dict):
            raise ContractError("the passed validation record is not an object")
        value = {**value, "attempt_id": str(value.get("attempt_id", attempt.get("attempt_id", "")))}
        if not validation_belongs_to(attempt, value):
            raise ContractError(
                "the validation record is not bound to this attempt's packet or implementing execution; "
                "a correction cannot inherit another attempt's pass"
            )
        if str(value.get("status", "")) != "passed":
            raise ContractError(
                f"the validation record says {value.get('status')!r}, not passed; refusing to record a pass"
            )
        revision = dict(validated_revision or value.get("validated_revision") or {})
        if not str(revision.get("implementation_fingerprint", "")).strip():
            raise ContractError(
                "a passed attempt validation needs its validated implementation fingerprint; "
                "an unbound pass cannot be used"
            )
        validation_path = str(path)
    else:
        revision = dict(validated_revision or {})
    existing = dict(attempt.get("validation") or {})
    if str(existing.get("status", "")) == "passed" and str(status) != "passed":
        raise ContractError("a recorded passing validation cannot be replaced by a failure")
    attempt["state"] = "validated" if status == "passed" else "failed"
    attempt["outcome"] = "validated" if status == "passed" else ("blocked" if status == "blocked" else "failed")
    attempt["validation"] = {
        "status": str(status),
        "failure_kind": str(failure_kind),
        "failure_reason": str(failure_reason),
        "path": str(validation_path),
        "validation_sha256": _file_sha256(validation_path) if str(validation_path) and Path(str(validation_path)).is_file() else "",
        "scope_status": str(scope_status),
        "retryable": bool(retryable),
        "validated_revision": revision,
        "commands": [dict(item) for item in commands],
        "skills": [dict(item) for item in skills],
        "recorded_at": contracts.utc_now(),
    }
    task["updated_at"] = contracts.utc_now()
    return attempt


def _file_sha256(path: str) -> str:
    import hashlib

    target = Path(str(path))
    return hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else ""


def record_review(task: dict, *, record: Mapping) -> dict:
    """Record the newest review while preserving every earlier one.

    The current review is the only one that can satisfy a gate; earlier records
    stay in ``reviews`` with their original outcome. A review is bound to the
    attempt and the validation digest it actually saw, so a review of an older
    revision cannot approve a newer one.
    """
    attempt = latest_attempt(task)
    previous = dict(task.get("review") or {})
    if previous and str(previous.get("review_id", "")) != str(record.get("review_id", "")):
        history = task.setdefault("reviews", [])
        if not any(str(item.get("review_id", "")) == str(previous.get("review_id", "")) for item in history):
            history.append(previous)
    task["review"] = {
        "review_id": str(record.get("review_id", "")),
        "outcome": str(record.get("outcome", "")),
        "recommendation": str(record.get("recommendation", "")),
        "reviewer_identity": str(record.get("reviewer_identity", "")),
        "independence_level": str(record.get("independence_level", "")),
        "findings": [str(item) for item in record.get("findings") or ()],
        "packet_id": str(record.get("packet_id", "")),
        "attempt_id": str(record.get("attempt_id", attempt.get("attempt_id", ""))),
        "task_id": str(record.get("task_id", task.get("task_id", ""))),
        "validation_sha256": str(record.get("validation_sha256", "")),
        "reviewed_revision": str(record.get("reviewed_revision", "")),
        "recorded_at": contracts.utc_now(),
    }
    # A new review is a new decision about a revision: any older proof receipt
    # no longer describes it and must not be used for acceptance.
    proof = dict(task.get("proof") or {})
    if proof and str(proof.get("review_id", "")) != str(record.get("review_id", "")):
        proof.update({
            "stale": True,
            "stale_reason": "a new independent review was recorded after this receipt",
        })
        task["proof"] = proof
    task["updated_at"] = contracts.utc_now()
    return task["review"]


def supersede_review(task: dict, *, reason: str) -> dict:
    """Retire the current review because a corrective attempt will replace it.

    The record is moved to ``reviews`` unchanged; the current slot is cleared so
    no gate can keep reading a passed review after the revision has moved.
    """
    current = dict(task.get("review") or {})
    if not current:
        return {}
    archived = {**current, "superseded_at": contracts.utc_now(), "superseded_reason": str(reason)}
    history = task.setdefault("reviews", [])
    if not any(str(item.get("review_id", "")) == str(archived.get("review_id", "")) for item in history):
        history.append(archived)
    task["review"] = {}
    task["updated_at"] = contracts.utc_now()
    return archived


def record_proof(task: dict, *, receipt: Mapping) -> dict:
    """Record the engine's receipt for the exact attempt and revision it proves."""
    attempt = latest_attempt(task)
    validation = dict(attempt.get("validation") or {})
    review = dict(task.get("review") or {})
    previous = dict(task.get("proof") or {})
    if previous and str(previous.get("proof_id", "")) != str(receipt.get("proof_id", "")):
        history = task.setdefault("proof_history", [])
        if not any(str(item.get("proof_id", "")) == str(previous.get("proof_id", "")) for item in history):
            history.append(previous)
    task["proof"] = {
        "proof_id": str(receipt.get("proof_id", "")),
        "acceptance_state": str(receipt.get("acceptance_state", "")),
        "work_digest": str(receipt.get("work_digest", "")),
        "requirements": len(receipt.get("requirements") or ()),
        "packet_id": str(receipt.get("packet_id", attempt.get("packet_id", ""))),
        "attempt_id": str(receipt.get("attempt_id", attempt.get("attempt_id", ""))),
        "validation_sha256": str(validation.get("validation_sha256", "")),
        "review_id": str(receipt.get("review_id", review.get("review_id", ""))),
        "implementation_fingerprint": str(receipt.get("implementation_fingerprint", "")),
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


# --------------------------------------------------------------- operations

def begin_operation(
    task: dict,
    *,
    kind: str,
    attempt_id: str = "",
    detail: str = "",
    operation_id: str = "",
) -> dict:
    """Record an operation *before* its side effect, for recovery.

    The caller persists the task after this returns. The same ``operation_id``
    may be supplied on a repeated resume: the existing record is returned rather
    than duplicated, which is what makes resume idempotent.
    """
    if kind not in TASK_OPERATION_KINDS:
        raise ContractError(f"unsupported task operation: {kind!r}")
    if operation_id:
        for item in task.get("operations") or ():
            if str(item.get("operation_id", "")) == str(operation_id):
                return item
    row = {
        "operation_id": operation_id or contracts.new_record_id("op"),
        "kind": str(kind),
        "attempt_id": str(attempt_id or (latest_attempt(task).get("attempt_id", ""))),
        "state": "started",
        "detail": str(detail),
        "started_at": contracts.utc_now(),
        "completed_at": "",
        "evidence": [],
    }
    rows = task.setdefault("operations", [])
    rows.append(row)
    if len(rows) > OPERATION_HISTORY_LIMIT:
        task["operations"] = rows[-OPERATION_HISTORY_LIMIT:]
    task["current_operation"] = str(row["operation_id"])
    task["updated_at"] = contracts.utc_now()
    return row


def start_operation(task: dict, *, kind: str, **options) -> dict:
    """Compatibility alias: an operation starts when it is first recorded."""
    return begin_operation(task, kind=kind, **options)


def complete_operation(
    task: dict,
    operation_id: str,
    *,
    detail: str = "",
    evidence: Sequence[str] = (),
) -> dict | None:
    for item in task.get("operations") or ():
        if str(item.get("operation_id", "")) != str(operation_id):
            continue
        if str(item.get("state")) not in ("started", "interrupted"):
            return item
        item.update({
            "state": "completed",
            "detail": str(detail or item.get("detail", "")),
            "evidence": [str(value) for value in evidence],
            "completed_at": contracts.utc_now(),
        })
        if str(task.get("current_operation", "")) == str(operation_id):
            task["current_operation"] = ""
        task["updated_at"] = contracts.utc_now()
        return item
    return None


def fail_operation(
    task: dict,
    operation_id: str,
    *,
    detail: str,
    evidence: Sequence[str] = (),
    state_value: str = "failed",
) -> dict | None:
    if state_value not in ("failed", "interrupted", "refused"):
        raise ContractError(f"unsupported operation outcome: {state_value!r}")
    for item in task.get("operations") or ():
        if str(item.get("operation_id", "")) != str(operation_id):
            continue
        if str(item.get("state")) == "completed":
            return item
        item.update({
            "state": str(state_value),
            "detail": str(detail),
            "evidence": [str(value) for value in evidence],
            "completed_at": contracts.utc_now(),
        })
        if str(task.get("current_operation", "")) == str(operation_id):
            task["current_operation"] = ""
        task["updated_at"] = contracts.utc_now()
        return item
    return None


def interrupted_operation(task: Mapping | None) -> dict:
    """The one operation that started and never recorded an outcome."""
    current = str((task or {}).get("current_operation", ""))
    for item in reversed((task or {}).get("operations") or ()):
        if str(item.get("operation_id", "")) == current and str(item.get("state")) == "started":
            return dict(item)
    for item in reversed((task or {}).get("operations") or ()):
        if str(item.get("state")) == "started":
            return dict(item)
    return {}


def last_durable_operation(task: Mapping | None) -> dict:
    rows = [item for item in (task or {}).get("operations") or () if isinstance(item, Mapping)]
    return dict(rows[-1]) if rows else {}


def started_operation(task: Mapping | None, kind: str) -> dict:
    """The newest started operation of one kind, if any."""
    for item in reversed((task or {}).get("operations") or ()):
        if str(item.get("kind", "")) == str(kind) and str(item.get("state")) == "started":
            return dict(item)
    return {}


# ------------------------------------------------------- evidence freshness

def validation_current_problems(
    task: Mapping,
    *,
    current_fingerprint: str = "",
    require_fingerprint: bool = True,
) -> list[str]:
    """Whether the latest attempt's validation still describes the live tree.

    The check is deliberately derived from records plus the caller's observed
    implementation fingerprint. An unbound validation is not accepted as
    current: a result that cannot be proven current is refused, not trusted.
    """
    task = task or {}
    attempt = latest_attempt(task)
    problems: list[str] = []
    if not attempt:
        return ["the task has no attempt record"]
    if str(attempt.get("state")) != "validated":
        problems.append(f"the latest attempt is {attempt.get('state') or 'unrecorded'}, not validated")
    validation = dict(attempt.get("validation") or {})
    if str(validation.get("status")) != "passed":
        problems.append("the latest attempt's validation did not pass")
    path = Path(str(validation.get("path", ""))) if validation.get("path") else None
    if path is None or not path.is_file():
        problems.append("the latest attempt's validation record is missing on disk")
    elif str(validation.get("validation_sha256", "")) and _file_sha256(str(path)) != str(
        validation.get("validation_sha256")
    ):
        problems.append("the validation record changed after it was recorded")
    revision = dict(validation.get("validated_revision") or {})
    recorded = str(revision.get("implementation_fingerprint", ""))
    if require_fingerprint:
        if not recorded:
            problems.append("the validation record has no implementation fingerprint; it cannot be proven current")
        elif not str(current_fingerprint or "").strip():
            problems.append("the current implementation fingerprint could not be established")
        elif recorded != str(current_fingerprint):
            problems.append(
                "the implementation changed after the validation ran; the recorded validation is stale"
            )
    return problems


def review_current_problems(task: Mapping, *, required: bool = True) -> list[str]:
    task = task or {}
    review = dict(task.get("review") or {})
    if not review:
        return ["the required independent review has not been recorded for the current attempt"] if required else []
    attempt = latest_attempt(task)
    if not review_belongs_to(task, review, attempt):
        return ["the recorded review is not bound to the current attempt and validation; it is stale"]
    if str(review.get("outcome")) != "passed":
        return [f"the current independent review outcome is {review.get('outcome') or 'unrecorded'}, not passed"]
    return []


def proof_current_problems(task: Mapping) -> list[str]:
    task = task or {}
    if not task.get("proof"):
        return ["the engine's Proof Pass receipt has not been recorded"]
    if not proof_is_current(task):
        return ["the recorded Proof Pass receipt belongs to an earlier attempt or revision and is stale"]
    return []


# ----------------------------------------------------------------- resume view

def task_status_value(
    task: Mapping,
    *,
    review_required: bool,
    rendered_required: bool | None = None,
    rendered_satisfied: bool | None = None,
    evidence_current: bool | None = None,
) -> str:
    """The derived state of one task from its records, nothing else.

    The latest attempt is authoritative. An earlier passing attempt never
    rescues a later failed correction, and an older review or proof receipt never
    speaks for a newer revision. ``rendered_required``/``rendered_satisfied``
    default to the task's own rendered ledger, so callers that only know about
    review keep working.
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
    attempt = latest_attempt(task)
    if evidence_current is False and (
        task.get("proof") or str(attempt.get("state", "")) == "validated"
    ):
        return "stale-evidence"
    if proof_is_current(task):
        return "verified"
    if not attempt:
        return "prepared"
    review = dict(task.get("review") or {})
    review_applies = review_belongs_to(task, review, attempt)
    if review_applies and str(review.get("outcome")) == "failed":
        return "review-failed"
    state_value = str(attempt.get("state", ""))
    if state_value == "prepared":
        return "prepared"
    if state_value == "running":
        return "worker-running"
    if state_value == "returned":
        return "returned"
    if state_value == "validated":
        if review_applies and str(review.get("outcome")) == "passed":
            return "validated"
        if rendered_required and not rendered_satisfied:
            return "render-pending"
        return "review-pending" if review_required else "validated"
    if state_value == "failed":
        validation = dict(attempt.get("validation") or {})
        if str(validation.get("failure_kind")) in (
            "contract", "out-of-scope", "dangerous-action", "repository-conflict", "worker-blocked"
        ):
            return "escalation-required"
        return "repair-pending" if validation.get("retryable") else "blocked"
    return "prepared"


def recovery_view(
    task: Mapping,
    *,
    review_required: bool,
    current_head: str = "",
    current_fingerprint: str = "",
    open_executions: Sequence[Mapping] = (),
) -> dict:
    """The durable recovery report for one task.

    It reports what is recorded, what was interrupted, and the single safe
    continuation. It never claims a worker finished because its process
    disappeared, and it never offers to replay a write whose effect cannot be
    established.
    """
    task = task or {}
    attempt = latest_attempt(task)
    operation = interrupted_operation(task)
    validation = dict(attempt.get("validation") or {})
    stale_problems = validation_current_problems(task, current_fingerprint=current_fingerprint)
    status_value = task_status_value(
        task, review_required=review_required, evidence_current=not stale_problems,
    )
    packet_path = Path(str(attempt.get("packet_path", ""))) if attempt else None
    return_path = packet_path / "evidence" / "return-handoff.md" if packet_path else None
    validation_path = packet_path / "evidence" / "validation.json" if packet_path else None
    review_recorded = bool(task.get("review")) and review_belongs_to(task, task.get("review"), attempt)
    review = dict(task.get("review") or {})
    safe = "inspect"
    human = ""
    if status_value in ("accepted", "rejected", "verified"):
        safe = "none"
    elif status_value == "worker-running":
        if return_path is not None and return_path.is_file():
            safe = "ingest-return"
        elif open_executions:
            safe = "wait-or-abandon-open"
            human = (
                "The worker execution is still open. Wait for it, or declare it lost with "
                "`task-run --abandon-open`; the engine will record a truthful interruption."
            )
        else:
            safe = "record-interruption"
    elif status_value == "returned":
        safe = "recover-validation" if validation_path is not None and validation_path.is_file() else "validate"
    elif status_value == "validated":
        stale = validation_current_problems(task, current_fingerprint=current_fingerprint)
        if stale:
            safe = "stop-stale-evidence"
            human = " ".join(stale) + " A new correction or task is required; the old pass cannot be reused."
        elif review_required and not review_recorded:
            safe = "review"
        elif review_required and str(review.get("outcome")) != "passed":
            safe = "prepare-review-correction"
        elif not task.get("proof"):
            safe = "proof"
        else:
            safe = "accept"
    elif status_value == "review-failed":
        safe = "prepare-review-correction"
    elif status_value == "stale-evidence":
        safe = "stop-stale-evidence"
        human = (
            "The implementation changed after the recorded validation. A new correction and a fresh "
            "validation are required; the old pass cannot be reused."
        )
    elif status_value == "repair-pending":
        safe = "repair"
    elif status_value == "prepared":
        safe = "run"
    elif status_value in ("blocked", "escalation-required"):
        safe = "escalate"
        human = "Inspect the recorded failure; routine repair is not authorized. Escalate deliberately or prepare a new task."
    revision = dict(validation.get("validated_revision") or {})
    return {
        "task_id": str(task.get("task_id", "")),
        "status": status_value,
        "current_attempt_id": str(attempt.get("attempt_id", "")),
        "current_packet_id": str(attempt.get("packet_id", "")),
        "attempt_state": str(attempt.get("state", "")),
        "last_durable_operation": last_durable_operation(task),
        "interrupted_operation": operation,
        "interrupted": bool(operation),
        "last_verified_revision": {
            "attempt_id": str(attempt.get("attempt_id", "")),
            "head": str(revision.get("head", "")),
            "implementation_fingerprint": str(revision.get("implementation_fingerprint", "")),
            "validation_sha256": str(validation.get("validation_sha256", "")),
        },
        "current_revision": {
            "head": str(current_head),
            "implementation_fingerprint": str(current_fingerprint),
            "matches_recorded": bool(
                not revision.get("implementation_fingerprint")
                or not current_fingerprint
                or str(revision.get("implementation_fingerprint")) == str(current_fingerprint)
            ),
        },
        "review": {
            "recorded": review_recorded,
            "outcome": str(review.get("outcome", "")),
            "review_id": str(review.get("review_id", "")),
        },
        "safe_continuation": safe,
        "required_human_action": human,
        "review_corrections": review_correction_count(task),
        "review_correction_limit": int(task.get("review_correction_limit", MAX_REVIEW_CORRECTIONS) or 0),
    }


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
        "review-failed": "the review found a real defect: prepare a review-directed correction (task-repair) and re-review the corrected revision",
        "verified": "the engine is done; the human acceptance decision remains (task-accept)",
        "accepted": "complete: the human accepted the verified result",
        "rejected": "the human rejected the result; repair or abandon deliberately",
        "blocked": "blocked: inspect the recorded failure and escalate or abandon deliberately",
        "escalation-required": "escalate to a stronger worker adapter or a human decision",
        "stale-evidence": "the implementation moved after validation; a new correction and fresh validation are required, never the old pass",
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
    "ADAPTER_CONFORMANCE_CHECKS",
    "adapter_conformance",
    "conformance_matrix",
    "adapter_view",
    "executable_available",
    "availability",
    "select_adapter",
    "preflight_required_capabilities",
    "TASK_SCHEMA",
    "TASK_STATES",
    "REPAIR_KINDS",
    "MAX_REVIEW_CORRECTIONS",
    "TASK_OPERATION_KINDS",
    "TASK_OPERATION_STATES",
    "attempt_id_for",
    "latest_attempt",
    "attempt_is_latest",
    "review_belongs_to",
    "validation_belongs_to",
    "proof_is_current",
    "review_is_current",
    "review_correction_count",
    "executor_identities",
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
    "attempt_scope_problems",
    "corrective_attempt_problems",
    "start_attempt",
    "record_attempt_return",
    "record_attempt_validation",
    "record_review",
    "supersede_review",
    "record_proof",
    "record_acceptance",
    "set_task_skill",
    "skills_missing_from_report",
    "parse_methods_section",
    "methods_report_problems",
    "evaluate_skill_evidence",
    "begin_operation",
    "start_operation",
    "complete_operation",
    "fail_operation",
    "interrupted_operation",
    "last_durable_operation",
    "started_operation",
    "validation_current_problems",
    "review_current_problems",
    "proof_current_problems",
    "task_status_value",
    "recovery_view",
    "review_is_required",
    "continuation_point",
]
