# 02 — Decision Graph

AR-205D makes decision dependencies executable with a deliberately small graph
(`ariadne_engine.decisions.graph`). It is not a workflow engine, not an agent
scheduler and not a second orchestration layer: a graph is a record, an outcome
is a record, and the graph never schedules anything by itself.

## Node shape

```
node
├── id                 unique within the graph
├── kind               DETERMINISTIC | DECISION_BATCH | GENERATION |
│                      VERIFICATION | HUMAN_GATE
├── dependencies       node ids whose outcomes this node consumes
├── state_projection   the declared projection contract (for decision nodes)
├── output_contract    the keys a SUCCEEDED outcome must carry, plus value
│                      conditions: a required key must be present and non-empty
│                      (False and 0 are values), an affirmed `verified: true` is
│                      mandatory for VERIFICATION nodes
├── fallback           the declared policy when the node cannot run
└── status             PENDING | READY | RUNNING | SUCCEEDED | FAILED |
                       BLOCKED | REFUSED | AWAITING_HUMAN |
                       AWAITING_GENERATION | INVALIDATED | SKIPPED
```

`from_plan` builds the canonical graph for a compiled plan: one deterministic
node per fact, one decision-batch node per dependency layer of bounded
questions, one generation node per generative need, verification nodes for the
declared obligations, and one human gate per protected action. A plan with
nothing left to ask produces a single verification node for the fast path.

## Execution semantics

* **Cycles are refused** at creation, and so is a dependency on a node that does
  not exist.
* **Only ready nodes are offered.** A node is ready when every dependency has
  `SUCCEEDED`; a pending node whose dependency failed is `BLOCKED` with the
  reason, never skipped.
* **Outcomes are immutable.** A terminal node cannot be rewritten. `FAILED`,
  `REFUSED` and `INVALIDATED` are outcomes too.
* **Completion is not success.** Graph progress counts completion separately from
  success, and a node is `SUCCEEDED` only when a caller recorded an explicit
  outcome satisfying its declared output contract. A handler that returns no
  status is a contract error.
* **Invalidation cascades.** Invalidating a node invalidates every dependent
  result transitively, because a result computed from a changed input is not a
  result. The whole closure is validated before anything is written: if any node
  in it is `RUNNING`, the call is refused and changes nothing, since a running
  action cannot be un-run.
* **Human gates stay human.** The engine cannot start a `HUMAN_GATE` node, and it
  cannot satisfy one: success requires a recorded human decision with an
  identity and a human channel, and a rejection is recorded as `REFUSED` rather
  than interpreted.
* **UNKNOWN stays unknown.** A node that cannot run is `BLOCKED` with a
  structured reason; nothing is silently skipped and no default answer is
  invented.

## Running ready work

`run_ready(state, graph_id, handlers)` executes ready, non-gate nodes through
registered handlers until a boundary stops it. Handlers receive
`(state, graph, node)` and return an outcome mapping. A kind with no registered
handler leaves the node ready with a structured reason — the run stops honestly
instead of guessing. `HUMAN_GATE` nodes are never offered to a handler.

## Batching inside the graph

A `DECISION_BATCH` node does not itself call a provider. The batch planner
resolves one dependency layer at a time: independent bounded questions that
share a projected state go into one call, and dependent questions live in later
layers. See [03 — State projections](03-STATE-PROJECTIONS.md) and
[01 — Decision Compiler](01-DECISION-COMPILER.md).

## Inspection

`execution_order` returns the deterministic topological layers (topological
order, not a schedule), `ready_nodes` and `blocked_nodes` report the frontier,
and `progress` reports counts, completion, success and open boundaries. The
benchmark cases in the `decision-graph` group exercise each of these rules,
including the adversarial ones.
