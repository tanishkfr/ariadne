"""The Decision Graph (AR-205D T2): a small dependency graph, not an orchestrator.

The graph exists so decision dependencies are *executable* instead of
documented: deterministic nodes, decision batches, generation, verification and
human gates are nodes; an edge means "this node's inputs include that node's
outcome". It deliberately reuses the engine's own state machinery — a graph is
a record, an outcome is a record, and the graph never schedules work by itself.

Semantics enforced here:

* cycles are refused and missing dependencies are refused, at creation time;
* only ready nodes (every dependency SUCCEEDED) are offered for execution;
* a node's outcome is immutable once terminal;
* invalidating a node transitively invalidates every dependent result, because a
  result computed from a changed input is not a result;
* a ``HUMAN_GATE`` node never completes by engine action: it needs a recorded
  human decision, and a rejection is refused rather than interpreted;
* node completion is not inferred as success. A node is ``SUCCEEDED`` only when
  a caller recorded an explicit outcome that satisfies its output contract;
* ``UNKNOWN`` stays unknown: a node that cannot run is ``BLOCKED`` with a
  structured reason, never skipped silently.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from .. import contracts
from ..contracts import (
    DECISION_GRAPH_NODE_KINDS,
    DECISION_GRAPH_STATUSES,
    DECISION_INTELLIGENCE_CONTRACT,
    SCHEMA_DECISION_INTELLIGENCE,
    ContractError,
)
from . import policy

TERMINAL_STATUSES = ("SUCCEEDED", "FAILED", "BLOCKED", "REFUSED", "INVALIDATED", "SKIPPED")
BOUNDARY_STATUSES = ("AWAITING_HUMAN", "AWAITING_GENERATION")
FAILED_DEPENDENCY_STATUSES = ("FAILED", "BLOCKED", "REFUSED", "INVALIDATED", "SKIPPED")

GraphHandler = Callable[[dict, dict, dict], Mapping]


def _node(
    node_id: str,
    kind: str,
    *,
    title: str = "",
    dependencies: Sequence[str] = (),
    projection: Mapping | None = None,
    output_contract: Mapping | None = None,
    fallback: Mapping | None = None,
) -> dict:
    if str(kind) not in DECISION_GRAPH_NODE_KINDS:
        raise ContractError(
            f"unsupported decision graph node kind {kind!r}; declared: "
            + ", ".join(DECISION_GRAPH_NODE_KINDS)
        )
    return {
        "id": str(node_id),
        "kind": str(kind),
        "title": str(title or node_id),
        "dependencies": [str(item) for item in dependencies],
        "state_projection": {str(key): value for key, value in dict(projection or {}).items()},
        "output_contract": {str(key): value for key, value in dict(output_contract or {}).items()},
        "fallback": {str(key): value for key, value in dict(fallback or {}).items()},
        "status": "PENDING",
        "attempts": 0,
        "outcome": {},
        "evidence": [],
        "reason": "",
        "updated_at": contracts.utc_now(),
    }


def create(
    state: dict,
    *,
    nodes: Sequence[Mapping],
    task_id: str = "",
    plan_id: str = "",
    stakes: str = "LOW",
) -> dict:
    """Create one decision graph record (validated, acyclic, dependency-closed)."""
    if not isinstance(state, dict):
        raise ContractError("a decision graph needs a run state object")
    if str(stakes) not in contracts.DECISION_CONSEQUENCES:
        raise ContractError(f"unsupported graph stakes: {stakes!r}")
    prepared: list[dict] = []
    for index, item in enumerate(nodes or ()):
        if not isinstance(item, Mapping):
            raise ContractError("a decision graph node must be a mapping")
        prepared.append(_node(
            str(item.get("id") or f"node-{index + 1}"),
            str(item.get("kind", "")),
            title=str(item.get("title", "")),
            dependencies=item.get("dependencies") or (),
            projection=item.get("state_projection"),
            output_contract=item.get("output_contract"),
            fallback=item.get("fallback"),
        ))
    record = {
        "schema_version": SCHEMA_DECISION_INTELLIGENCE,
        "graph_id": contracts.new_record_id("dcg"),
        "run_id": str(state.get("run_id", "")),
        "task_id": str(task_id),
        "plan_id": str(plan_id),
        "stakes": str(stakes),
        "nodes": prepared,
        "status": "PENDING",
        "policy_version": policy.POLICY_VERSION,
        "contract_version": DECISION_INTELLIGENCE_CONTRACT,
        "authorization_effect": "none",
        "recorded_at": contracts.utc_now(),
    }
    problems = contracts.decision_graph_record_problems(record)
    if problems:
        raise ContractError("the decision graph is invalid: " + "; ".join(problems))
    contracts.require_collection_capacity(state, "decision_graphs")
    state.setdefault("decision_graphs", []).append(record)
    return record


def graph(state: Mapping, graph_id: str) -> dict:
    for record in state.get("decision_graphs") or []:
        if isinstance(record, Mapping) and str(record.get("graph_id", "")) == str(graph_id):
            return dict(record)
    raise ContractError(f"no decision graph matches {graph_id!r}")


def graphs(state: Mapping, *, task_id: str = "") -> list[dict]:
    rows = [
        dict(record) for record in (state.get("decision_graphs") or [])
        if isinstance(record, Mapping)
        and (not task_id or str(record.get("task_id", "")) == str(task_id))
    ]
    return rows


def node(graph_record: Mapping, node_id: str) -> dict:
    for item in graph_record.get("nodes") or []:
        if str(item.get("id", "")) == str(node_id):
            return dict(item)
    raise ContractError(f"no node {node_id!r} in this decision graph")


def _require_node(graph_record: Mapping, node_id: str) -> dict:
    for item in graph_record.get("nodes") or []:
        if str(item.get("id", "")) == str(node_id):
            return item
    raise ContractError(f"no node {node_id!r} in this decision graph")


def _stored(state: Mapping, graph_id: str) -> dict:
    for record in state.get("decision_graphs") or []:
        if isinstance(record, Mapping) and str(record.get("graph_id", "")) == str(graph_id):
            return record
    raise ContractError(f"no decision graph matches {graph_id!r}")


def ready_nodes(graph_record: Mapping) -> list[dict]:
    """Nodes whose every dependency has SUCCEEDED and which have not started."""
    statuses = {str(item["id"]): str(item.get("status", "")) for item in graph_record.get("nodes") or []}
    ready: list[dict] = []
    for item in graph_record.get("nodes") or []:
        if str(item.get("status", "")) not in ("PENDING", "READY"):
            continue
        if all(statuses.get(str(dep), "") == "SUCCEEDED" for dep in item.get("dependencies") or ()):
            ready.append(dict(item))
    return ready


def blocked_nodes(graph_record: Mapping) -> list[dict]:
    """Pending nodes whose dependency set contains a non-successful terminal node."""
    statuses = {str(item["id"]): str(item.get("status", "")) for item in graph_record.get("nodes") or []}
    blocked: list[dict] = []
    for item in graph_record.get("nodes") or []:
        if str(item.get("status", "")) not in ("PENDING", "READY"):
            continue
        failures = sorted(
            str(dep) for dep in item.get("dependencies") or ()
            if statuses.get(str(dep), "") in FAILED_DEPENDENCY_STATUSES
        )
        if failures:
            blocked.append({**dict(item), "blocked_by": failures})
    return blocked


def execution_order(graph_record: Mapping) -> list[list[str]]:
    """Deterministic topological layers, for inspection (not a scheduler)."""
    dependencies = {
        str(item["id"]): {str(dep) for dep in item.get("dependencies") or ()}
        for item in graph_record.get("nodes") or []
    }
    remaining = set(dependencies)
    layers: list[list[str]] = []
    resolved: set[str] = set()
    while remaining:
        layer = sorted(key for key in remaining if not (dependencies[key] - resolved))
        if not layer:
            raise ContractError("the decision graph contains a cycle")
        layers.append(layer)
        resolved.update(layer)
        remaining -= set(layer)
    return layers


def _settle(graph_record: Mapping) -> None:
    statuses = [str(item.get("status", "")) for item in graph_record.get("nodes") or []]
    if any(status in BOUNDARY_STATUSES for status in statuses):
        graph_record["status"] = "AWAITING"
    elif any(status in ("FAILED", "REFUSED") for status in statuses):
        graph_record["status"] = "ATTENTION"
    elif any(status == "INVALIDATED" for status in statuses):
        graph_record["status"] = "INVALIDATED"
    elif statuses and all(status == "SUCCEEDED" for status in statuses):
        graph_record["status"] = "SUCCEEDED"
    elif statuses and all(status in TERMINAL_STATUSES for status in statuses):
        graph_record["status"] = "CLOSED_INCOMPLETE"
    else:
        graph_record["status"] = "ACTIVE"


def mark_running(state: dict, graph_id: str, node_id: str) -> dict:
    graph_record = _stored(state, graph_id)
    item = _require_node(graph_record, node_id)
    if str(item.get("status", "")) not in ("PENDING", "READY"):
        raise ContractError(f"node {node_id} is {item.get('status')}; only a pending node can start")
    statuses = {str(row["id"]): str(row.get("status", "")) for row in graph_record.get("nodes") or []}
    not_ready = sorted(
        str(dep) for dep in item.get("dependencies") or () if statuses.get(str(dep), "") != "SUCCEEDED"
    )
    if not_ready:
        raise ContractError(
            f"node {node_id} is not ready; dependencies not successful: {', '.join(not_ready)}"
        )
    if str(item.get("kind", "")) == "HUMAN_GATE":
        raise ContractError(
            f"node {node_id} is a human gate; the engine cannot start it, it awaits a human decision"
        )
    item["status"] = "RUNNING"
    item["attempts"] = int(item.get("attempts", 0) or 0) + 1
    item["updated_at"] = contracts.utc_now()
    _settle(graph_record)
    return item


def _empty_value(value: Any) -> bool:
    """Whether an outcome value is absent evidence rather than a value.

    ``False`` and ``0`` are values (a failed check and a counted zero are both
    meaningful facts); ``None``, blank strings and empty collections are not.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def _output_contract_satisfied(item: Mapping, outcome: Mapping) -> list[str]:
    contract = item.get("output_contract") if isinstance(item.get("output_contract"), Mapping) else {}
    required = [str(key) for key in contract.get("required", [])]
    must_be_true = [str(key) for key in contract.get("true", [])]
    unsatisfied: list[str] = []
    for key in required:
        if key not in outcome or _empty_value(outcome.get(key)):
            unsatisfied.append(key)
    for key in must_be_true:
        if outcome.get(key) is not True:
            unsatisfied.append(key)
    if str(item.get("kind", "")) == "VERIFICATION" and outcome.get("verified") is not True:
        unsatisfied.append("verified")
    return sorted(dict.fromkeys(unsatisfied))


def mark_outcome(
    state: dict,
    graph_id: str,
    node_id: str,
    *,
    status: str,
    outcome: Mapping | None = None,
    reason: str = "",
    evidence: Sequence[str] = (),
    human_decision: Mapping | None = None,
) -> dict:
    """Record one terminal node outcome. Immutable once written."""
    graph_record = _stored(state, graph_id)
    item = _require_node(graph_record, node_id)
    if str(item.get("status", "")) in TERMINAL_STATUSES:
        raise ContractError(
            f"node {node_id} already finished as {item.get('status')}; an outcome is immutable"
        )
    status = str(status)
    if status not in TERMINAL_STATUSES and status not in BOUNDARY_STATUSES:
        raise ContractError(
            f"unsupported node outcome {status!r}; declared: "
            + ", ".join((*TERMINAL_STATUSES, *BOUNDARY_STATUSES))
        )
    if status in (*BOUNDARY_STATUSES, "SUCCEEDED"):
        statuses = {str(row["id"]): str(row.get("status", "")) for row in graph_record.get("nodes") or []}
        not_done = sorted(
            str(dep) for dep in item.get("dependencies") or () if statuses.get(str(dep), "") != "SUCCEEDED"
        )
        if status == "SUCCEEDED" and not_done:
            raise ContractError(
                f"node {node_id} cannot succeed before its dependencies: {', '.join(not_done)}"
            )
    if str(item.get("kind", "")) == "HUMAN_GATE":
        if status == "SUCCEEDED":
            if not isinstance(human_decision, Mapping):
                raise ContractError(
                    f"node {node_id} is a human gate; it succeeds only with a recorded human decision"
                )
            if not str(human_decision.get("identity", "")).strip():
                raise ContractError("a human gate decision must record the human identity, verbatim")
            if str(human_decision.get("channel", "")) not in ("human-cli", "human"):
                raise ContractError(
                    "a human gate decision arrives through a human channel; engine or provider "
                    "output cannot satisfy it"
                )
            if human_decision.get("approved") is not True:
                status = "REFUSED"
        elif status not in ("AWAITING_HUMAN", "REFUSED", "BLOCKED", "INVALIDATED"):
            raise ContractError(
                f"a human gate node cannot reach {status!r} by engine action; it awaits the human"
            )
    if status == "SUCCEEDED":
        missing = _output_contract_satisfied(item, dict(outcome or {}))
        if missing:
            raise ContractError(
                f"node {node_id} cannot succeed without its declared output: {', '.join(missing)}"
            )
    item["status"] = status
    item["outcome"] = {str(key): value for key, value in dict(outcome or {}).items()}
    item["reason"] = str(reason)
    item["evidence"] = [str(value) for value in evidence]
    if isinstance(human_decision, Mapping):
        item["human_decision"] = {str(key): value for key, value in human_decision.items()}
    item["updated_at"] = contracts.utc_now()
    _settle(graph_record)
    return item


def record_human_decision(
    state: dict,
    graph_id: str,
    node_id: str,
    *,
    identity: str,
    approved: bool,
    note: str = "",
) -> dict:
    """The explicit human path for a HUMAN_GATE node.

    This records the decision; it does not fabricate authorization beyond the
    gate it belongs to. The approval system remains the authority for gates.
    """
    return mark_outcome(
        state, graph_id, node_id,
        status="SUCCEEDED" if approved else "REFUSED",
        outcome={"approved": bool(approved), "note": str(note)},
        reason="human decision recorded" if approved else "the human declined this gate",
        human_decision={
            "identity": str(identity),
            "channel": "human-cli",
            "approved": bool(approved),
            "note": str(note),
        },
    )


def invalidate(state: dict, graph_id: str, node_id: str, *, reason: str) -> list[str]:
    """Invalidate one node and every dependent result, transitively.

    The whole closure is validated before anything is written, so a refused
    invalidation changes nothing. A running node anywhere in the closure
    refuses the call: its side effect cannot be un-run, so the caller must wait
    for the outcome and invalidate then. Traversal continues through nodes that
    are already invalidated, because their dependents may still hold results
    computed from the invalid input.
    """
    if not str(reason or "").strip():
        raise ContractError("an invalidation must record why it is invalid")
    graph_record = _stored(state, graph_id)
    _require_node(graph_record, node_id)
    closure: list[str] = []
    seen: set[str] = set()
    queue = [str(node_id)]
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        target = _require_node(graph_record, current)
        if str(target.get("status", "")) == "RUNNING":
            raise ContractError(
                f"node {current} is running; a running action cannot be invalidated, await its outcome"
            )
        closure.append(current)
        for row in graph_record.get("nodes") or []:
            if current in {str(dep) for dep in row.get("dependencies") or ()}:
                queue.append(str(row["id"]))
    invalidated: list[str] = []
    for current in closure:
        target = _require_node(graph_record, current)
        if str(target.get("status", "")) == "INVALIDATED":
            continue
        target["status"] = "INVALIDATED"
        target["reason"] = f"invalidated because {node_id}: {reason}"
        target["updated_at"] = contracts.utc_now()
        invalidated.append(current)
    _settle(graph_record)
    return invalidated


def progress(graph_record: Mapping) -> dict:
    """Status counts and completion. Completion is not success."""
    counts: dict[str, int] = {}
    for item in graph_record.get("nodes") or []:
        key = str(item.get("status", ""))
        counts[key] = counts.get(key, 0) + 1
    total = len(graph_record.get("nodes") or [])
    succeeded = counts.get("SUCCEEDED", 0)
    settled = sum(counts.get(status, 0) for status in TERMINAL_STATUSES)
    return {
        "nodes": total,
        "statuses": dict(sorted(counts.items())),
        "completed": settled,
        "succeeded": succeeded,
        "complete": total > 0 and settled == total,
        "success": total > 0 and succeeded == total,
        "boundaries": sum(counts.get(status, 0) for status in BOUNDARY_STATUSES),
        "note": "completion is not success: only explicit SUCCEEDED outcomes count",
    }


def run_ready(state: dict, graph_id: str, *, handlers: Mapping[str, GraphHandler]) -> list[dict]:
    """Execute ready nodes through registered handlers until a boundary stops it.

    Handlers receive ``(state, graph, node)`` and return a mapping with at least
    ``status``. No handler may reach a human gate: a gate always stops. A node
    with no handler stays ready with a structured reason — never skipped, never
    inferred successful.
    """
    executed: list[dict] = []
    while True:
        graph_record = _stored(state, graph_id)
        candidates = ready_nodes(graph_record)
        if not candidates:
            break
        progressed = False
        for candidate in candidates:
            kind = str(candidate.get("kind", ""))
            if kind == "HUMAN_GATE":
                continue
            handler = (handlers or {}).get(kind)
            if handler is None:
                continue
            if str(candidate.get("status", "")) != "RUNNING":
                mark_running(state, graph_id, candidate["id"])
            result = dict(handler(state, _stored(state, graph_id), candidate) or {})
            if "status" not in result:
                raise ContractError(
                    f"the handler for node {candidate['id']} returned no status; completion is not success"
                )
            item = mark_outcome(
                state, graph_id, candidate["id"],
                status=str(result["status"]),
                outcome=result.get("outcome") or {},
                reason=str(result.get("reason", "")),
                evidence=result.get("evidence") or (),
                human_decision=result.get("human_decision"),
            )
            executed.append(dict(item))
            progressed = True
        if not progressed:
            break
    return executed


def pending_reason(graph_record: Mapping, *, handlers: Mapping[str, GraphHandler] | None = None) -> str:
    """Why a graph that is neither successful nor settled has stopped."""
    progress_view = progress(graph_record)
    if progress_view["success"]:
        return "every node succeeded"
    boundaries = [
        str(item.get("id")) for item in graph_record.get("nodes") or []
        if str(item.get("status", "")) in BOUNDARY_STATUSES
    ]
    if boundaries:
        return "awaiting a boundary: " + ", ".join(boundaries)
    blocked = blocked_nodes(graph_record)
    if blocked:
        return "blocked by failed dependencies: " + ", ".join(
            f"{item['id']}<-{','.join(item['blocked_by'])}" for item in blocked
        )
    ready = ready_nodes(graph_record)
    if ready and handlers is not None:
        missing = sorted({str(item.get("kind")) for item in ready if str(item.get("kind")) not in handlers})
        if missing:
            return "no handler is registered for: " + ", ".join(missing)
    if ready:
        return "ready nodes are waiting: " + ", ".join(str(item["id"]) for item in ready)
    return "the graph is settled"


def from_plan(
    state: dict,
    plan_record: Mapping,
    *,
    handlers_kind_map: Mapping[str, str] | None = None,
) -> dict:
    """Build the canonical graph for a compiled decision plan.

    Deterministic checks, one decision-batch node per dependency step, one
    generation node per generative need, a verification node when the plan
    declares verification obligations, and a human gate when the plan protects
    an action. The graph is bounded by construction: no meta-agents.
    """
    kind_map = {str(key): str(value) for key, value in dict(handlers_kind_map or {}).items()}
    del kind_map  # reserved for a future per-requirement kind override; the default map is canonical
    nodes: list[dict] = []
    node_id_for: dict[str, str] = {}
    for fact in plan_record.get("deterministic_facts") or []:
        fact_id = str(fact.get("fact_id", ""))
        node_id_for[fact_id] = f"fact:{fact_id}"
        nodes.append({
            "id": node_id_for[fact_id],
            "kind": "DETERMINISTIC",
            "title": str(fact.get("statement") or fact.get("kind") or "deterministic fact"),
            "output_contract": {"required": ["value"]},
            "fallback": {"policy": "deterministic"},
        })
    questions = [item for item in plan_record.get("bounded_questions") or []]
    layer_of: dict[str, int] = {}
    pending = {
        str(item.get("requirement_id", "")): {str(dep) for dep in item.get("depends_on") or []}
        for item in questions
    }
    resolved: set[str] = set()
    layer_index = 0
    while pending:
        ready = sorted(key for key, deps in pending.items() if not (deps - resolved))
        if not ready:
            raise ContractError("the compiled decision plan contains a cycle between bounded questions")
        layer_index += 1
        for key in ready:
            layer_of[key] = layer_index
            pending.pop(key)
        resolved.update(ready)
    for item in questions:
        requirement_id = str(item.get("requirement_id", ""))
        question_id = str(item.get("question_id", requirement_id))
        node_id_for[requirement_id] = f"batch:{layer_of.get(requirement_id, 1)}:{question_id}"
        nodes.append({
            "id": node_id_for[requirement_id],
            "kind": "DECISION_BATCH",
            "title": str(item.get("instructions", ""))[:120],
            "dependencies": [
                node_id_for[dep] for dep in (item.get("depends_on") or ())
                if str(dep) in node_id_for
            ],
            "state_projection": {"contract_id": item.get("projection_contract", "")},
            "output_contract": {"required": ["answer"]},
            "fallback": {"policy": "deterministic-fallback"},
        })
    for need in plan_record.get("generative_needs") or []:
        requirement_id = str(need.get("requirement_id", ""))
        nodes.append({
            "id": f"generate:{requirement_id}",
            "kind": "GENERATION",
            "title": str(need.get("kind") or "generation"),
            "dependencies": [
                node_id_for[str(dep)] for dep in (
                    next(
                        (
                            item.get("depends_on") or ()
                            for item in questions
                            if str(item.get("requirement_id", "")) == requirement_id
                        ),
                        (),
                    )
                )
                if str(dep) in node_id_for
            ],
            "fallback": {"policy": "escalate"},
        })
    for index, obligation in enumerate(plan_record.get("verification_requirements") or [], start=1):
        nodes.append({
            "id": f"verify:{index}",
            "kind": "VERIFICATION",
            "title": str(obligation.get("claim") or obligation.get("subject") or "verification"),
            "output_contract": {"required": ["verified"], "true": ["verified"]},
            "fallback": {"policy": "escalate"},
        })
    for item in plan_record.get("protected_actions") or []:
        nodes.append({
            "id": f"human:{item.get('requirement_id') or item.get('kind')}",
            "kind": "HUMAN_GATE",
            "title": str(item.get("statement") or "human gate"),
            "fallback": {"policy": "human"},
        })
    if not nodes:
        nodes.append({
            "id": "fast-path",
            "kind": "VERIFICATION",
            "title": "deterministic validation of the fast path",
            "output_contract": {"required": ["verified"], "true": ["verified"]},
            "fallback": {"policy": "escalate"},
        })
    graph_record = create(
        state,
        nodes=nodes,
        task_id=str(plan_record.get("task_id", "")),
        plan_id=str(plan_record.get("plan_id", "")),
        stakes=str(plan_record.get("stakes", "LOW")),
    )
    return graph_record


def layer_dependencies(plan_record: Mapping, requirement_id: str) -> list[str]:
    for item in plan_record.get("bounded_questions") or []:
        if str(item.get("requirement_id", "")) == str(requirement_id):
            return [str(dep) for dep in item.get("depends_on") or []]
    return []


def summarise(state: Mapping) -> dict:
    rows = [record for record in (state.get("decision_graphs") or []) if isinstance(record, Mapping)]
    statuses: dict[str, int] = {}
    for record in rows:
        key = str(record.get("status", ""))
        statuses[key] = statuses.get(key, 0) + 1
    return {
        "graphs": len(rows),
        "statuses": dict(sorted(statuses.items())),
        "nodes": sum(len(record.get("nodes") or []) for record in rows),
        "note": "a graph awaiting a human or generation boundary is not a completed graph",
    }


__all__ = [
    "TERMINAL_STATUSES",
    "BOUNDARY_STATUSES",
    "FAILED_DEPENDENCY_STATUSES",
    "create",
    "graph",
    "graphs",
    "node",
    "ready_nodes",
    "blocked_nodes",
    "execution_order",
    "mark_running",
    "mark_outcome",
    "record_human_decision",
    "invalidate",
    "progress",
    "run_ready",
    "pending_reason",
    "from_plan",
    "layer_dependencies",
    "summarise",
]
