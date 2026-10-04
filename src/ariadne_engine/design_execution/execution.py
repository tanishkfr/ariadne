"""Running a grounded implementation: implement, validate mechanically, repair, escalate.

The lifecycle is Ariadne's existing S4B lifecycle with a design step inserted, not a
new state machine. The bounded-repair arithmetic comes from
``statemachine.worker_transition_for`` and ``policy.repair_allowed`` so there is one
repair budget in this codebase rather than two that disagree:

```text
IMPLEMENT
    â†“
MECHANICAL VALIDATION  (build Â· typecheck Â· lint Â· tests Â· static accessibility)
    â†“ fail
REPAIR #1 â†’ VALIDATE
    â†“ fail
REPAIR #2 â†’ ESCALATE
```

Three properties are load-bearing:

* **No infinite design retries.** The budget is the existing
  ``MAX_ROUTINE_REPAIRS``. Exhausting it is escalation, not another attempt.
* **A groundless result is not a valid result.** A run whose changes carry
  ``UNGROUNDED_DESIGN_CHANGE`` cannot reach ``MECHANICALLY_VALIDATED`` no matter how
  green the build is. Passing checks say the code compiles; they say nothing about
  whether the design was traceable, so the two are separate gates.
* **No source-only claim of visual acceptance.** The highest outcome AR-221 can
  record is ``MECHANICALLY_VALIDATED``, and the run stores an explicit
  ``visual_acceptance: NOT_CLAIMED`` with its reason. Judging appearance needs
  rendered evidence this phase does not gather.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .. import contracts
from ..contracts import ContractError
from . import changes as changes_module
from . import grounding as grounding_module
from . import inventory as inventory_module
from . import packet as packet_module
from . import plan as plan_module

VALIDATION_TIMEOUT_SECONDS = 600
"""Upper bound on one mechanical validation command.

Matches the transport's own ceiling. A design implementation is allowed to run a
build; it is not allowed to hang while doing it.
"""

NOT_CLAIMED_REASON = (
    "source inspection establishes that code exists and passes its checks. It cannot establish that "
    "the result looks or behaves like the approved direction; that judgement needs rendered evidence, "
    "which is out of scope for this phase"
)
"""Why AR-221 never records a visual-acceptance claim of its own."""


class ValidationRunner:
    """Run a plan's validation requirements as bounded argv inside the project.

    The commands come from the plan, and the plan's commands were already turned
    into argv by the transport allowlist at compile time. Re-checked here rather than
    trusted, because the second reader of a plan should not have to assume the first
    one was careful.

    Uses ``shell=False``, a list argv, and ``stdin`` closed. There is no branch in
    this class that reaches a shell, which is what makes a reference's "run npm
    install" text an inert string instead of a delayed problem.

    Closing stdin is not tidiness. A child that inherits the parent's stdin and
    decides to read it will block for as long as that stdin stays open - which, under
    a supervisor or a CI harness, is until something else times out. The whole run
    then looks like a hang in a check that had already finished.
    """

    def __init__(
        self,
        *,
        project: Path | str,
        timeout_seconds: int = VALIDATION_TIMEOUT_SECONDS,
        run: Callable[..., subprocess.CompletedProcess] | None = None,
    ) -> None:
        self.project = Path(project)
        self.timeout = max(1, min(int(timeout_seconds), VALIDATION_TIMEOUT_SECONDS))
        self._run = run or subprocess.run

    def run(self, requirements: Sequence[Mapping]) -> dict:
        """Execute every required check and report each one honestly."""
        from .. import policy

        transport = policy.transport_tool()
        rows: list[dict] = []
        for requirement in requirements or ():
            if not isinstance(requirement, Mapping):
                continue
            argv = [str(item) for item in requirement.get("argv") or []]
            command = str(requirement.get("command", ""))
            if not argv:
                verified, reason = transport.safe_validation_argv(command)
                if verified is None:
                    rows.append({
                        "check_id": str(requirement.get("check_id", "")),
                        "command": command,
                        "status": "BLOCKED",
                        "returncode": None,
                        "reason": f"refused by the transport boundary: {reason}",
                        "stdout_sha256": "", "stderr_sha256": "",
                    })
                    continue
                argv = verified
            resolved = _resolve_executable(argv[0], self.project)
            if resolved is None:
                rows.append({
                    "check_id": str(requirement.get("check_id", "")),
                    "command": command, "status": "BLOCKED", "returncode": None,
                    "reason": f"the check's executable {argv[0]!r} is not on PATH",
                    "stdout_sha256": "", "stderr_sha256": "",
                })
                continue
            argv = [resolved, *argv[1:]]
            try:
                completed = self._run(
                    argv, cwd=self.project, capture_output=True, text=True,
                    timeout=self.timeout, shell=False, stdin=subprocess.DEVNULL,
                )
            except subprocess.TimeoutExpired:
                rows.append({
                    "check_id": str(requirement.get("check_id", "")),
                    "command": command, "status": "FAILED", "returncode": None,
                    "reason": f"the check exceeded {self.timeout}s and was stopped",
                    "stdout_sha256": "", "stderr_sha256": "",
                })
                continue
            except OSError as exc:
                rows.append({
                    "check_id": str(requirement.get("check_id", "")),
                    "command": command, "status": "BLOCKED", "returncode": None,
                    "reason": f"the check could not be started: {exc}",
                    "stdout_sha256": "", "stderr_sha256": "",
                })
                continue
            except ContractError as exc:
                # A capability that is absent is a first-class answer. Letting it
                # escape would turn "no toolchain" into a crashed run, and a crashed
                # run reports less than "the check could not run, here is why".
                rows.append({
                    "check_id": str(requirement.get("check_id", "")),
                    "command": command, "status": "BLOCKED", "returncode": None,
                    "reason": str(exc),
                    "stdout_sha256": "", "stderr_sha256": "",
                })
                continue
            rows.append({
                "check_id": str(requirement.get("check_id", "")),
                "command": command,
                "status": "PASSED" if completed.returncode == 0 else "FAILED",
                "returncode": int(completed.returncode),
                "reason": "",
                "stdout_sha256": _digest(str(completed.stdout or "")),
                "stderr_sha256": _digest(str(completed.stderr or "")),
                "stdout_tail": _tail(str(completed.stdout or "")),
                "stderr_tail": _tail(str(completed.stderr or "")),
            })
        required = [
            row for row in rows
            if any(
                str(item.get("command", "")) == row["command"] and item.get("required")
                for item in requirements if isinstance(item, Mapping)
            )
        ]
        selected = required or rows
        failed = [row for row in selected if row["status"] != "PASSED"]
        return {
            "status": "PASSED" if not failed else "FAILED",
            "checks": rows,
            "required_failed": [row["command"] for row in failed],
            "attempt_note": (
                "every check's exit status is recorded; output is stored as digests plus a short tail "
                "because the artifact, not the transcript, is the evidence"
            ),
        }


_EXECUTABLE_CACHE: dict[tuple[str, str], str | None] = {}
"""Resolved argv[0] per (name, working directory), for the life of the process.

Not an optimisation. On Windows ``shutil.which`` walks every ``PATH`` entry calling
``os.path.exists``, and one slow or disconnected entry can block for tens of seconds.
Called once per check per repair attempt - which is what this runner used to do - a
single run could spend minutes resolving the same name over and over. The answer
cannot change while the process runs, so it is asked once.

A miss is cached too: a name that is not on ``PATH`` will not appear while the process
is running, and re-walking ``PATH`` to learn that again is pure cost.
"""


def _resolve_executable(name: str, project: Path | None = None) -> str | None:
    """Resolve an argv[0] to something the OS can start, without a shell.

    On Windows the package managers are ``.cmd`` shims, and ``CreateProcess`` cannot
    start a bare ``npm``. :func:`shutil.which` applies ``PATHEXT`` and returns the
    real file, which starts with ``shell=False`` - verified, not assumed.

    This only resolves a *path*. The argv shape was already vetted by
    ``safe_validation_argv``, and nothing here adds an argument, drops one, or hands
    a line to a shell interpreter. Without it, every package-manager check on Windows
    reports ``BLOCKED`` and a grounded implementation can never be mechanically
    validated on the platform Ariadne ships on.
    """
    import shutil

    name = str(name)
    if "/" in name or "\\" in name:
        return name
    # The key is built from plain strings on purpose. Constructing a Path here to
    # normalise the directory was measurably the most expensive thing in the whole
    # validation loop - pathlib re-parses and re-formats every component - and it
    # bought nothing, because the answer depends on the name and the directory, not
    # on their spelling.
    key = (name.lower(), "" if project is None else str(project))
    if key not in _EXECUTABLE_CACHE:
        _EXECUTABLE_CACHE[key] = shutil.which(name)
    return _EXECUTABLE_CACHE[key]


def _digest(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def _tail(text: str, limit: int = 1200) -> str:
    body = text.strip()
    return body[-limit:] if len(body) > limit else body


def record_run(
    state: dict,
    *,
    plan: Mapping,
    outcome: str,
    validation_attempts: Sequence[Mapping],
    telemetry: Mapping,
    acceptance: Mapping | None = None,
    escalation_reason: str = "",
    started_at: str = "",
    finished_at: str = "",
    run_record_id: str = "",
    constraint_exposure: Sequence[Mapping] = (),
) -> dict:
    """Append one implementation run record, validated like every other design record."""
    record = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "run_record_id": str(run_record_id or contracts.new_record_id("dir")),
        "run_id": str(state.get("run_id", "")),
        "plan_id": str(plan.get("plan_id", "")),
        "task_id": str(plan.get("task_id", "")),
        "started_at": str(started_at or contracts.utc_now()),
        "finished_at": str(finished_at or contracts.utc_now()),
        "outcome": str(outcome),
        "validation_attempts": [dict(row) for row in validation_attempts],
        "escalation_reason": str(escalation_reason),
        "constraint_exposure": [dict(row) for row in constraint_exposure],
        "telemetry": dict(telemetry),
        "acceptance": dict(acceptance or {"visual_acceptance": "NOT_CLAIMED", "reason": NOT_CLAIMED_REASON}),
        "provenance": {"created_by": "engine", "policy_version": contracts.POLICY_VERSION},
    }
    problems = contracts.implementation_run_problems(record)
    if problems:
        raise ContractError("implementation run is malformed: " + "; ".join(problems))
    contracts.require_design_capacity(state, "design_implementation_runs")
    state.setdefault("design_implementation_runs", []).append(record)
    return record


def runs(state: Mapping, *, plan_id: str = "") -> list[dict]:
    values = state.get("design_implementation_runs")
    if not isinstance(values, list):
        return []
    return [
        dict(item) for item in values
        if isinstance(item, Mapping) and (not plan_id or str(item.get("plan_id", "")) == str(plan_id))
    ]


def worker_transition(validation_status: str, *, attempts: int = 0, repair_limit: int = 2) -> dict:
    """Classify a validation result with the engine's existing worker transition.

    Delegating is the point. A design-specific repair counter would be a second
    budget that could disagree with the one S4B enforces, and the disagreement would
    show up as an infinite design retry loop exactly when a project is already stuck.

    Both vocabularies are accepted - the runner's ``PASSED``/``FAILED``/``BLOCKED``
    and the state machine's own lowercase form - because an earlier version keyed the
    lookup on one spelling and defaulted everything else to ``blocked``. A typo then
    became an escalation, which is the quietest possible way to misreport why a run
    stopped. An unrecognised value is refused instead.
    """
    from .. import statemachine

    value = str(validation_status or "").strip()
    status = {
        "PASSED": "passed", "FAILED": "failed", "BLOCKED": "blocked",
        "passed": "passed", "failed": "failed", "blocked": "blocked",
    }.get(value, "")
    if not status:
        raise ContractError(
            f"unknown validation status {validation_status!r}; expected PASSED, FAILED or BLOCKED. "
            "Guessing here would report the wrong reason for stopping"
        )
    return statemachine.worker_transition_for(
        status, failure_kind="routine", repair_attempts=int(attempts), repair_limit=int(repair_limit)
    )


def run_grounded_implementation(
    state: dict,
    *,
    plan: Mapping,
    project: Path | str,
    inventory: Mapping,
    references_by_id: Mapping[str, Mapping],
    implemented_changes: Sequence[Mapping],
    validation_runner: ValidationRunner | None = None,
    allowed_scope: Sequence[str] = (),
    forbidden_scope: Sequence[str] = (),
    emit: Callable[..., object] | None = None,
    started_at: str = "",
) -> dict:
    """Classify, validate, repair-bound and record one grounded implementation.

    ``implemented_changes`` is what the implementer actually did, as a list of
    ``{"path", "before", "after", "constraint_ids", "reference_ids", "principle_ids",
    "requirement_ids", "treatment", "implementation_source", "change_kind"}``. The
    engine classifies each against the plan and records the verdict; it does not take
    the implementer's word for any of it.

    The two gates are independent and both must pass:

    1. **mechanical** - every required validation command exited 0;
    2. **grounding** - no change carries an ungrounded, cloning or accessibility
       verdict.

    A green build with an ungrounded design change is the exact outcome this phase
    exists to catch, and it is reported as ``ESCALATED`` rather than
    ``MECHANICALLY_VALIDATED``.
    """
    project_root = Path(project)
    root = project_root.resolve()
    plan_identifier = str(plan.get("plan_id", ""))
    if not plan_identifier:
        raise ContractError("a grounded implementation needs a plan")
    emitted = emit or (lambda *_a, **_k: None)

    emitted("design_implementation_started", state=state, task_id=str(plan.get("task_id", "")),
            plan_id=plan_identifier, direction_id=str(plan.get("direction_id", "")))

    worker_packet = packet_module.build_worker_packet(
        state, plan=plan, inventory=inventory, references_by_id=references_by_id,
        allowed_scope=allowed_scope, forbidden_scope=forbidden_scope,
    )
    packet_problems = packet_module.packet_problems(worker_packet)
    if packet_problems:
        raise ContractError(
            "the worker packet for this plan is malformed: " + "; ".join(packet_problems)
        )

    recorded: list[dict] = []
    verdicts: dict[str, int] = {}
    for change in implemented_changes or ():
        if not isinstance(change, Mapping):
            raise ContractError("an implemented change must be a mapping")
        relative = str(change.get("path", ""))
        before = str(change.get("before", ""))
        after = str(change.get("after", ""))
        contained = _resolve(root, relative)
        classification = grounding_module.classify_change(
            path=relative,
            before=before,
            after=after,
            plan=plan,
            declared_constraint_ids=[str(item) for item in change.get("constraint_ids") or []],
            declared_reference_ids=[str(item) for item in change.get("reference_ids") or []],
            declared_treatment=str(change.get("treatment", "")),
        )
        if contained is None:
            classification = {
                **classification,
                "verdict": "OUT_OF_SCOPE",
                "problem": f"{relative} does not resolve inside the project root",
                "explanation": (
                    "path traversal, an absolute path and a symlink escaping the project are refused "
                    "before the change is even classified; a design reference cannot point writes at a "
                    "file the project does not own"
                ),
            }
        elif not allowed_scope or not _within_scope(relative, allowed_scope):
            classification = {
                **classification,
                "verdict": "OUT_OF_SCOPE",
                "problem": (
                    f"{relative} is outside the permitted scope "
                    f"({', '.join(str(item) for item in allowed_scope)})"
                ),
                "explanation": (
                    "a design request does not authorise unrelated work. A change outside the "
                    "permitted files is refused whatever its quality"
                ),
            }
        record = changes_module.record_change(
            state,
            plan=plan,
            path=relative,
            classification=classification,
            change_kind=str(change.get("change_kind", "")),
            requirement_ids=[str(item) for item in change.get("requirement_ids") or []],
            principle_ids=[str(item) for item in change.get("principle_ids") or []],
            reference_ids=[str(item) for item in change.get("reference_ids") or []],
            implementation_source=str(change.get("implementation_source", "")),
            component_name=str(change.get("component", "")),
        )
        recorded.append(record)
        verdicts[str(record["verdict"])] = verdicts.get(str(record["verdict"]), 0) + 1
        emitted(
            "design_implementation_change_recorded",
            state=state, task_id=str(plan.get("task_id", "")),
            path=relative, verdict=str(record["verdict"]),
            constraint_ids=list(record.get("constraint_ids") or []),
        )
        if str(record["verdict"]) == "UNGROUNDED_DESIGN_CHANGE":
            emitted(
                "design_implementation_ungrounded_change",
                state=state, task_id=str(plan.get("task_id", "")),
                path=relative, categories=dict(record.get("categories") or {}),
                problem=str(record.get("problem", "")),
            )

    blocking = {
        "UNGROUNDED_DESIGN_CHANGE", "ACCESSIBILITY_REGRESSION",
        "REFERENCE_CLONING", "OUT_OF_SCOPE",
    }
    blocked_paths = sorted({
        str(row.get("path", "")) for row in recorded if str(row.get("verdict")) in blocking
    })

    runner = validation_runner or ValidationRunner(project=project_root)
    requirements = [row for row in plan.get("validation_requirements") or [] if isinstance(row, Mapping)]
    attempts: list[dict] = []
    transition = worker_transition("PASSED")
    attempt_index = 0
    while True:
        result = runner.run(requirements)
        attempts.append({"attempt": attempt_index, **result})
        transition = worker_transition(result["status"], attempts=attempt_index,
                                       repair_limit=_repair_limit())
        if transition["to"] == "validated":
            break
        if transition["to"] == "escalation-required":
            break
        attempt_index += 1

    mechanically_validated = bool(attempts) and attempts[-1]["status"] == "PASSED"
    if blocked_paths:
        outcome = "ESCALATED"
        reason = (
            "the implementation produced "
            + ", ".join(sorted(blocking & set(verdicts)))
            + f" on {', '.join(blocked_paths)}. Mechanical validation does not make an ungrounded design "
            "change acceptable, so the run stops here for a human"
        )
    elif mechanically_validated:
        outcome = "MECHANICALLY_VALIDATED"
        reason = ""
    elif not recorded:
        outcome = "REFUSED"
        reason = "the implementation changed nothing, so there is nothing to validate"
    else:
        outcome = "ESCALATED"
        reason = (
            "mechanical validation did not pass inside the bounded repair budget: "
            + str(transition.get("next", ""))
        )

    summary = changes_module.change_summary(recorded)
    exposure = _constraint_exposure(plan, recorded, implemented_changes or ())
    telemetry = _telemetry(
        inventory=inventory,
        worker_packet=worker_packet,
        summary=summary,
        attempts=attempts,
        plan=plan,
        state=state,
    )
    run_record = record_run(
        state,
        plan=plan,
        outcome=outcome,
        validation_attempts=attempts,
        telemetry=telemetry,
        escalation_reason=reason,
        started_at=str(started_at or contracts.utc_now()),
        constraint_exposure=exposure,
    )
    if outcome == "MECHANICALLY_VALIDATED":
        emitted("design_implementation_validated", state=state,
                task_id=str(plan.get("task_id", "")), plan_id=plan_identifier,
                checks=len(attempts[-1]["checks"]))
    elif outcome == "ESCALATED":
        emitted("design_implementation_escalated", state=state,
                task_id=str(plan.get("task_id", "")), plan_id=plan_identifier, reason=reason)
    return {
        "run_record": run_record,
        "changes": recorded,
        "verdicts": verdicts,
        "blocked_paths": blocked_paths,
        "worker_packet": worker_packet,
        "outcome": outcome,
        "escalation_reason": reason,
        "transition": transition,
        "validation": attempts[-1] if attempts else {},
        "acceptance": run_record["acceptance"],
        "trace": changes_module.trace(state, plan_id=plan_identifier, exposure=exposure),
        "note": (
            "the highest outcome available here is mechanical validation. Whether the result looks "
            "like the approved direction is a separate question, asked from rendered evidence this "
            "phase does not collect"
        ),
    }


def _repair_limit() -> int:
    from .. import policy

    try:
        return int(policy.transport_tool().MAX_ROUTINE_REPAIRS)
    except Exception:  # noqa: BLE001 - the limit is a constant, not a dependency
        return 2


def _constraint_exposure(
    plan: Mapping, recorded: Sequence[Mapping], changes: Sequence[Mapping]
) -> list[dict]:
    """Which plan constraints were exercised, and which hold because nothing violated them.

    A constraint like "the accent comes from the project's token, never a literal" is
    satisfied by nobody writing a literal colour. Demanding a file that demonstrates
    that absence would push authors to invent a change so the trace looked tidy, so the
    run instead records ``VERIFIED_BY_ABSENCE`` with the detectors it checked and the
    files it checked them in.

    A constraint with no detectors and no citing change is reported ``NOT_EXERCISED``
    and stays a gap. Nothing here can excuse a constraint it cannot actually check.
    """
    cited = {
        str(constraint_id)
        for row in recorded
        for constraint_id in (row.get("constraint_ids") or [])
    }
    files = sorted({str(row.get("path", "")) for row in recorded if str(row.get("path", ""))})
    bodies = {str(row.get("path", "")): str(row.get("after", "")) for row in changes}
    rows: list[dict] = []
    for row in plan.get("constraints") or []:
        if not isinstance(row, Mapping):
            continue
        constraint_id = str(row.get("constraint_id", ""))
        if not constraint_id or constraint_id in cited:
            continue
        detectors = [str(item) for item in row.get("detectors") or [] if str(item)]
        if detectors:
            violated = sorted({
                detector for detector in detectors
                for path in files
                if detector in bodies.get(path, "")
            })
            rows.append({
                "constraint_id": constraint_id,
                "outcome": "VIOLATED" if violated else "VERIFIED_BY_ABSENCE",
                "detectors": detectors,
                "files_checked": files,
                "detectors_present": violated,
            })
            continue
        rows.append({
            "constraint_id": constraint_id,
            "outcome": "NOT_EXERCISED",
            "detectors": [],
            "files_checked": [],
            "detail": (
                "this constraint states a positive obligation and nothing implemented it; there is "
                "nothing to check it against"
            ),
        })
    return rows


def _resolve(root: Path, relative: str) -> Path | None:
    """Resolve a reported change path inside the project, or refuse it."""
    from ..design_reference import safety

    try:
        return safety.contained_path(relative, root, label=f"implementation path {relative}")
    except ContractError:
        return None


def _within_scope(relative: str, allowed: Sequence[str]) -> bool:
    """Whether a project-relative path is inside the permitted scope.

    Delegates to the engine's existing matcher rather than restating it. A bare
    directory name does not authorise its contents, which is the rule that stops a
    handoff listing ``src`` from authorising a rewrite of everything in it.
    """
    normalised = str(relative).replace("\\", "/")
    return any(contracts.path_matches(normalised, str(pattern)) for pattern in allowed)


def _telemetry(
    *,
    inventory: Mapping,
    worker_packet: Mapping,
    summary: Mapping,
    attempts: Sequence[Mapping],
    plan: Mapping,
    state: Mapping,
) -> dict:
    """What happened, with unknowns left unknown.

    No cost, no saving and no quality figure appears here, because none was measured.
    What is recorded is counts and measured bytes; anything the run could not observe
    is reported as ``UNKNOWN`` rather than as zero, which would read as a fact.
    """
    reuse = [row for row in plan.get("component_reuse_decisions") or [] if isinstance(row, Mapping)]
    decisions: dict[str, int] = {}
    for row in reuse:
        decisions[str(row.get("decision", ""))] = decisions.get(str(row.get("decision", "")), 0) + 1
    references = [
        row for row in plan.get("implementation_references") or [] if isinstance(row, Mapping)
    ]
    attribution = worker_packet.get("context_attribution") if isinstance(
        worker_packet.get("context_attribution"), Mapping
    ) else {}
    checks = [row for attempt in attempts for row in attempt.get("checks") or [] if isinstance(row, Mapping)]
    failed_checks = [row for row in checks if str(row.get("status")) != "PASSED"]
    return {
        "files_inspected": int(inventory.get("component_files_scanned", 0) or 0),
        "components_discovered": len(inventory.get("components") or []),
        "components_reused": decisions.get("REUSE_PROJECT_COMPONENT", 0),
        "components_adapted": decisions.get("ADAPT_PROJECT_COMPONENT", 0),
        "components_from_registry": decisions.get("USE_APPROVED_REGISTRY_COMPONENT", 0),
        "components_created": decisions.get("BUILD_CUSTOM_COMPONENT", 0),
        "external_implementation_references_used": len(references),
        "dependencies_requested": 0,
        "dependencies_approved": 0,
        "dependencies_installed": 0,
        "material_changes": int(summary.get("material", 0)),
        "grounded_material_changes": int(summary.get("grounded_material", 0)),
        "ungrounded_material_changes": int(summary.get("ungrounded_material", 0)),
        "validation_attempts": len(attempts),
        "validation_checks": len(checks),
        "repair_attempts": max(0, len(attempts) - 1),
        "failed_checks": len(failed_checks),
        "context_bytes": {
            "raw_reference_bytes_available": int(attribution.get("raw_reference_bytes_available", 0) or 0),
            "reference_bytes_transported": int(attribution.get("reference_bytes_transported", 0) or 0),
            "worker_packet_bytes": int(attribution.get("worker_packet_bytes", 0) or 0),
        },
        "unknown": [
            "whether the result looks like the approved direction: not measured by this phase",
            "runtime or browser behaviour: no rendered check was run",
        ],
    }


def summarise_run(record: Mapping) -> str:
    """A short human view of one implementation run."""
    telemetry = record.get("telemetry") if isinstance(record.get("telemetry"), Mapping) else {}
    bytes_block = telemetry.get("context_bytes") if isinstance(telemetry.get("context_bytes"), Mapping) else {}
    lines = [
        f"Implementation run {record.get('run_record_id')}  outcome: {record.get('outcome')}",
        f"  plan: {record.get('plan_id')}",
        f"  validation attempts: {telemetry.get('validation_attempts', 'UNKNOWN')} "
        f"(repairs: {telemetry.get('repair_attempts', 'UNKNOWN')})",
        f"  material changes: {telemetry.get('material_changes', 'UNKNOWN')}, "
        f"grounded: {telemetry.get('grounded_material_changes', 'UNKNOWN')}, "
        f"ungrounded: {telemetry.get('ungrounded_material_changes', 'UNKNOWN')}",
        f"  reference bytes transported: {bytes_block.get('reference_bytes_transported', 'UNKNOWN')} of "
        f"{bytes_block.get('raw_reference_bytes_available', 'UNKNOWN')} available",
        f"  visual acceptance: {str((record.get('acceptance') or {}).get('visual_acceptance', 'UNKNOWN'))}",
    ]
    if record.get("escalation_reason"):
        lines.append(f"  escalated: {record.get('escalation_reason')}")
    return "\n".join(lines)


__all__ = [
    "NOT_CLAIMED_REASON",
    "VALIDATION_TIMEOUT_SECONDS",
    "ValidationRunner",
    "record_run",
    "run_grounded_implementation",
    "runs",
    "summarise_run",
    "worker_transition",
]
