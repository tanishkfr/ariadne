"""AR-205D deterministic benchmark cases: decision intelligence as an execution mechanism.

Every case is offline, deterministic and dependency-free. They test whether the
engine asks *the right kind of question* before it spends intelligence:

* code before judgment — a fact code can establish never becomes a model call;
* bounded judgment before generation — a closed answer space is a decision, not
  a prompt;
* batching independent questions, staging dependent ones;
* caching only state/question/provider/model/policy-bound decisions;
* escalating uncertainty rather than disguising it;
* and keeping confidence separate from authority.

The cases drive the engine modules directly through the runtime module
(``ctx.repo.module("ariadne.py")``), which is the same engine the CLI and the API
use; nothing here re-implements an engine rule.
"""

from __future__ import annotations

from .cases import Ctx, Outcome, case

# --------------------------------------------------------------- helpers

FRONTEND_HANDOFF = (
    "# HANDOFF\n\n## Worker execution contract\n\n| Field | Value |\n| --- | --- |\n| Role | bulk |\n\n"
    "## Permitted scope\n\n| Path | Change |\n| --- | --- |\n"
    "| src/pages/landing.tsx | build the landing page |\n\n"
    "## Validation commands\n\n| Command | Expected |\n| --- | --- |\n| npm test | pass |\n"
)

REVISION = "ab" * 32


def runtime(ctx: Ctx):
    return ctx.repo.module("ariadne.py")


def project_box(ctx: Ctx):
    box = ctx.sandbox()
    box.write("HANDOFF.md", FRONTEND_HANDOFF)
    box.write("PROJECT.md", "# PROJECT\n\nA small product site.\n")
    return box


def bench_state(box, **extra) -> dict:
    state = {
        "schema_version": 1,
        "run_id": "bench-ar205d",
        "project": str(box.project),
        "run_root": str(box.run_root),
        "packets": [{"id": "bench-S4B", "stage": "S4B", "path": str(box.run_root / "bench-S4B")}],
        "approvals": [],
    }
    state.update(extra)
    return state


def deterministic(module, script, *, model_version="1", provider="deterministic-fixture"):
    return module.DECISIONS.providers.DeterministicProvider(
        script=script, provider=provider, model_version=model_version,
    )


FAILURE_SCRIPT = {
    "failure-class": {
        "answer": "IMPLEMENTATION_FAILURE", "confidence": 0.8,
        "confidence_kind": "DERIVED_CONFIDENCE",
    },
}


def failure_projection(module, source="mystery", detail="the command failed"):
    return module.DECISIONS.projections.build(
        "failure-classification", entries={"failure": {"source": source, "detail": detail}},
    )


def classification_question(module, **overrides):
    options = {
        "question_id": "failure-class",
        "instructions": "Classify the failure into exactly one declared class.",
        "options": module.CONTRACTS.DECISION_CLASSIFIABLE_FAILURE_CLASSES,
        "consequence": "LOW",
        "projection_contract": "failure-classification",
    }
    options.update(overrides)
    return module.DECISIONS.contracts.DecisionQuestion(**options)


# ============================================================ decision compiler


@case(
    id="decision-compiler.deterministic-fact-wins",
    group="decision-compiler",
    title="A fact code already knows never becomes a model call",
    task="Compile a plan whose requirement carries a deterministically established value.",
    expectation="The requirement classifies DETERMINISTIC with reason CODE_KNOWS, no question is created and no provider is consulted.",
    evaluation="Compile the plan with a counting provider and read the classifications and the fact reason.",
    evidence_required="The plan record and the empty provider call log.",
    layer="deterministic",
)
def compiler_deterministic(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    counting = deterministic(module, FAILURE_SCRIPT)
    plan = module.DECISIONS.compiler.compile_plan(
        state,
        requirements=[{
            "requirement_id": "file", "kind": "file-exists", "known": True,
            "statement": "main.py exists", "value": True,
        }],
        task_id="bench-S4B", decision_provider=counting,
    )
    problems = []
    if plan["classifications"]["DETERMINISTIC"] != 1:
        problems.append(f"classifications={plan['classifications']}")
    if plan["bounded_questions"]:
        problems.append("a known fact created a bounded question")
    if plan["deterministic_facts"][0]["reason"] != "CODE_KNOWS":
        problems.append(f"reason={plan['deterministic_facts'][0]['reason']}")
    if counting.calls:
        problems.append(f"the provider was consulted {len(counting.calls)} time(s) for an exact fact")
    if plan["economics"]["model_calls_avoided_by_deterministic"] != 1:
        problems.append("the structural avoidance was not counted")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"DETERMINISTIC={plan['classifications']['DETERMINISTIC']} questions={len(plan['bounded_questions'])}",
        evidence={"plan": plan, "provider_calls": counting.calls, "problems": problems},
        metrics={"model_calls": 0, "questions": 0},
    )


@case(
    id="decision-compiler.bounded-classification",
    group="decision-compiler",
    title="A closed-answer judgement classifies BOUNDED with a projection contract",
    task="Compile a failure-class requirement.",
    expectation="It classifies BOUNDED with the failure-classification projection, a consequence and no authorization effect.",
    evaluation="Compile the plan and read the bounded question record.",
    evidence_required="The plan and its bounded question.",
    layer="deterministic",
)
def compiler_bounded(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    plan = module.DECISIONS.compiler.compile_plan(
        state,
        requirements=[{"requirement_id": "failure-class", "kind": "failure-class"}],
        task_id="bench-S4B", decision_provider=deterministic(module, FAILURE_SCRIPT),
    )
    question = plan["bounded_questions"][0]
    problems = []
    if plan["classifications"]["BOUNDED"] != 1:
        problems.append(f"classifications={plan['classifications']}")
    if question["projection_contract"] != "failure-classification":
        problems.append(f"contract={question['projection_contract']}")
    if question["consequence"] != "LOW" or question["classification"] != "BOUNDED":
        problems.append(f"question={question}")
    if plan["authorization_effect"] != "none":
        problems.append("the plan claims an authorization effect")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"BOUNDED contract={question['projection_contract']}",
        evidence={"plan": plan, "problems": problems},
        metrics={"questions": 1},
    )


@case(
    id="decision-compiler.generative-needs-a-declared-reason",
    group="decision-compiler",
    title="Generation is only compiled with a declared reason",
    task="Compile an implementation requirement that genuinely requires creation.",
    expectation="It classifies GENERATIVE with CREATION_REQUIRED and is counted as a required generative call.",
    evaluation="Compile the plan and read the generative need and economics.",
    evidence_required="The plan and its generative need.",
    layer="deterministic",
)
def compiler_generative(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    plan = module.DECISIONS.compiler.compile_plan(
        state,
        requirements=[{"requirement_id": "impl", "kind": "implementation"}],
        task_id="bench-S4B", decision_provider=deterministic(module, FAILURE_SCRIPT),
        generative_available=True,
    )
    need = plan["generative_needs"][0]
    problems = []
    if plan["classifications"]["GENERATIVE"] != 1 or need["reason"] != "CREATION_REQUIRED":
        problems.append(f"need={need}")
    if plan["economics"]["generative_calls_required"] != 1:
        problems.append("a required generative call was not counted")
    refusal = ""
    try:
        module.DECISIONS.compiler.compile_plan(
            state, requirements=[{"requirement_id": "x", "kind": "implementation",
                                  "generative_reason": "because"}],
            task_id="bench-S4B", decision_provider=deterministic(module, FAILURE_SCRIPT),
        )
    except module.CONTRACTS.ContractError as exc:
        refusal = str(exc)
    if "declared generation reason" not in refusal:
        problems.append(f"an undeclared generation reason was accepted: {refusal}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"GENERATIVE reason={need['reason']}",
        evidence={"plan": plan, "problems": problems},
        metrics={"model_calls": 0, "generative_required": 1},
    )


@case(
    id="decision-compiler.human-is-policy-not-confidence",
    group="decision-compiler",
    title="A policy-reserved choice classifies HUMAN regardless of any provider",
    task="Compile a release-approval requirement with a provider configured.",
    expectation="It classifies HUMAN, appears as a protected action, and no bounded question is created for it.",
    evaluation="Compile the plan and read the classification and protected actions.",
    evidence_required="The plan and its protected action.",
    layer="deterministic",
)
def compiler_human(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    plan = module.DECISIONS.compiler.compile_plan(
        state,
        requirements=[{"requirement_id": "release", "kind": "release-approval"}],
        task_id="bench-S4B", decision_provider=deterministic(module, FAILURE_SCRIPT),
    )
    problems = []
    if plan["classifications"]["HUMAN"] != 1:
        problems.append(f"classifications={plan['classifications']}")
    if not plan["protected_actions"]:
        problems.append("a human requirement produced no protected action")
    if any(item["kind"] == "release-approval" for item in plan["bounded_questions"]):
        problems.append("a human requirement was also compiled as a bounded question")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"HUMAN protected={len(plan['protected_actions'])}",
        evidence={"plan": plan, "problems": problems},
        metrics={"model_calls": 0},
    )


@case(
    id="decision-compiler.unresolved-never-silently-generative",
    group="decision-compiler",
    title="An unclassifiable requirement is UNRESOLVED, never GENERATIVE",
    task="Compile a requirement kind the rule table does not declare.",
    expectation="It classifies UNRESOLVED with UNRESOLVED_CLASSIFICATION and creates no generative need.",
    evaluation="Compile the plan and read the classification and escalation reason.",
    evidence_required="The plan and its escalation entry.",
    layer="deterministic",
)
def compiler_unresolved(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    plan = module.DECISIONS.compiler.compile_plan(
        state,
        requirements=[{"requirement_id": "mystery", "kind": "not-a-declared-kind"}],
        task_id="bench-S4B", decision_provider=deterministic(module, FAILURE_SCRIPT),
        generative_available=True,
    )
    problems = []
    if plan["classifications"]["UNRESOLVED"] != 1:
        problems.append(f"classifications={plan['classifications']}")
    if plan["generative_needs"]:
        problems.append("an unresolved requirement silently became generative")
    if plan["escalations"][0]["reason"] != "UNRESOLVED_CLASSIFICATION":
        problems.append(f"escalations={plan['escalations']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"UNRESOLVED escalations={len(plan['escalations'])}",
        evidence={"plan": plan, "problems": problems},
        metrics={"model_calls": 0},
    )


# =============================================================== decision graph


@case(
    id="decision-graph.compiled-plan-is-acyclic-and-ready-ordered",
    group="decision-graph",
    title="A compiled plan produces a valid acyclic graph in dependency order",
    task="Compile a plan with a dependent bounded question and a protected action, then build the graph.",
    expectation="The graph validates, is acyclic, and the dependent node is not ready until its input succeeds.",
    evaluation="Build the graph from the plan and inspect the execution order and ready nodes.",
    evidence_required="The graph record and the ready-node sets before and after the input completes.",
    layer="deterministic",
)
def graph_from_plan(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    plan = module.DECISIONS.compiler.compile_plan(
        state,
        requirements=[
            {"requirement_id": "first", "kind": "failure-class", "question_id": "first-question"},
            {"requirement_id": "second", "kind": "remediation-family", "question_id": "second-question",
             "depends_on": ["first"]},
            {"requirement_id": "release", "kind": "release-approval"},
        ],
        task_id="bench-S4B", decision_provider=deterministic(module, FAILURE_SCRIPT),
    )
    graph = module.DECISIONS.graph.from_plan(state, plan)
    problems = []
    if module.CONTRACTS.decision_graph_record_problems(graph):
        problems.append(f"graph problems={module.CONTRACTS.decision_graph_record_problems(graph)}")
    order = module.DECISIONS.graph.execution_order(graph)
    if not any(node.startswith("batch:1") for node in order[0]):
        problems.append(f"the independent question is not in the first layer: {order}")
    ready_ids = {node["id"] for node in module.DECISIONS.graph.ready_nodes(graph)}
    dependent = [node for node in graph["nodes"] if node["id"] == "batch:2:second-question"]
    if not dependent or dependent[0]["id"] in ready_ids:
        problems.append(f"the dependent question was ready before its input: {ready_ids}")
    first = next(node for node in graph["nodes"] if node["id"] == "batch:1:first-question")
    module.DECISIONS.graph.mark_running(state, graph["graph_id"], first["id"])
    module.DECISIONS.graph.mark_outcome(
        state, graph["graph_id"], first["id"], status="SUCCEEDED", outcome={"answer": "x"},
    )
    ready_ids = {node["id"] for node in module.DECISIONS.graph.ready_nodes(module.DECISIONS.graph.graph(state, graph["graph_id"]))}
    if "batch:2:second-question" not in ready_ids:
        problems.append("the dependent question did not become ready after its input succeeded")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"layers={len(order)} nodes={len(graph['nodes'])}",
        evidence={"graph": graph, "order": order, "problems": problems},
        metrics={"model_calls": 0},
    )


@case(
    id="decision-graph.cycle-and-missing-dependency-refused",
    group="decision-graph",
    title="A cycle or a missing dependency is refused at creation",
    task="Attempt to create a cyclic graph and a graph naming a node that does not exist.",
    expectation="Both attempts raise a contract error naming the cycle or the missing dependency.",
    evaluation="Attempt each creation and read the refusal messages.",
    evidence_required="The two refusal messages.",
    layer="deterministic",
)
def graph_cycle(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    cycle_message = ""
    missing_message = ""
    try:
        module.DECISIONS.graph.create(state, nodes=[
            {"id": "x", "kind": "DETERMINISTIC", "dependencies": ["y"]},
            {"id": "y", "kind": "DETERMINISTIC", "dependencies": ["x"]},
        ])
    except module.CONTRACTS.ContractError as exc:
        cycle_message = str(exc)
    try:
        module.DECISIONS.graph.create(state, nodes=[
            {"id": "x", "kind": "DETERMINISTIC", "dependencies": ["ghost"]},
        ])
    except module.CONTRACTS.ContractError as exc:
        missing_message = str(exc)
    problems = []
    if "cycle" not in cycle_message:
        problems.append(f"cycle message={cycle_message!r}")
    if "missing dependencies" not in missing_message:
        problems.append(f"missing message={missing_message!r}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual="cycle and missing dependency refused",
        evidence={"cycle": cycle_message, "missing": missing_message, "problems": problems},
        metrics={"model_calls": 0},
    )


@case(
    id="decision-graph.outcome-is-immutable-and-needs-its-output",
    group="decision-graph",
    title="A node cannot succeed without its declared output, and an outcome is immutable",
    task="Complete a decision-batch node without an answer, then try to rewrite a terminal fact node.",
    expectation="The output-less success is refused and the terminal outcome cannot be rewritten.",
    evaluation="Attempt the two transitions and read the refusals.",
    evidence_required="The refusal messages.",
    layer="deterministic",
)
def graph_outcome_contract(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    graph = module.DECISIONS.graph.create(state, nodes=[
        {"id": "fact", "kind": "DETERMINISTIC", "output_contract": {"required": ["value"]}},
        {"id": "batch", "kind": "DECISION_BATCH", "dependencies": ["fact"],
         "output_contract": {"required": ["answer"]}},
    ])
    module.DECISIONS.graph.mark_outcome(
        state, graph["graph_id"], "fact", status="SUCCEEDED", outcome={"value": True},
    )
    output_message = ""
    try:
        module.DECISIONS.graph.mark_outcome(
            state, graph["graph_id"], "batch", status="SUCCEEDED", outcome={"note": "done"},
        )
    except module.CONTRACTS.ContractError as exc:
        output_message = str(exc)
    immutable_message = ""
    try:
        module.DECISIONS.graph.mark_outcome(
            state, graph["graph_id"], "fact", status="FAILED",
        )
    except module.CONTRACTS.ContractError as exc:
        immutable_message = str(exc)
    problems = []
    if "declared output" not in output_message or "answer" not in output_message:
        problems.append(f"output message={output_message!r}")
    if "immutable" not in immutable_message:
        problems.append(f"immutable message={immutable_message!r}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual="output contract enforced and outcome immutable",
        evidence={"output": output_message, "immutable": immutable_message, "problems": problems},
        metrics={"model_calls": 0},
    )


@case(
    id="decision-graph.invalidation-cascades",
    group="decision-graph",
    title="Invalidating an input invalidates every dependent result",
    task="Complete two dependent nodes, change the input, and invalidate it.",
    expectation="Both nodes become INVALIDATED, completion is not success, and a running node refuses invalidation.",
    evaluation="Invalidate the completed input and inspect the statuses and graph progress.",
    evidence_required="The invalidated node ids and the graph progress.",
    layer="deterministic",
)
def graph_invalidation(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    graph = module.DECISIONS.graph.create(state, nodes=[
        {"id": "a", "kind": "DETERMINISTIC", "output_contract": {"required": ["value"]}},
        {"id": "b", "kind": "DECISION_BATCH", "dependencies": ["a"], "output_contract": {"required": ["answer"]}},
        {"id": "c", "kind": "VERIFICATION", "dependencies": ["b"], "output_contract": {"required": ["verified"]}},
    ])
    module.DECISIONS.graph.mark_outcome(state, graph["graph_id"], "a", status="SUCCEEDED", outcome={"value": 1})
    module.DECISIONS.graph.mark_outcome(state, graph["graph_id"], "b", status="SUCCEEDED", outcome={"answer": "x"})
    module.DECISIONS.graph.mark_running(state, graph["graph_id"], "c")
    running_message = ""
    try:
        module.DECISIONS.graph.invalidate(state, graph["graph_id"], "b", reason="the input changed")
    except module.CONTRACTS.ContractError as exc:
        running_message = str(exc)
    module.DECISIONS.graph.mark_outcome(state, graph["graph_id"], "c", status="FAILED", reason="interrupted")
    invalidated = module.DECISIONS.graph.invalidate(
        state, graph["graph_id"], "a", reason="the revision changed",
    )
    progress = module.DECISIONS.graph.progress(module.DECISIONS.graph.graph(state, graph["graph_id"]))
    problems = []
    if not {"a", "b", "c"} <= set(invalidated):
        problems.append(f"invalidated={invalidated}")
    if "running" not in running_message:
        problems.append(f"running message={running_message!r}")
    if progress["success"] is True:
        problems.append("an invalidated graph still reports success")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"invalidated={','.join(invalidated)} complete={progress['completed']}/{progress['nodes']}",
        evidence={"progress": progress, "problems": problems},
        metrics={"model_calls": 0},
    )


@case(
    id="decision-graph.protected-human-boundary-holds",
    group="decision-graph",
    title="A human gate cannot be started, satisfied or bypassed by engine action",
    task="Attempt to start a human gate, satisfy it with engine evidence, then record a human rejection.",
    expectation="Both engine attempts are refused; the human rejection is recorded as REFUSED, never success.",
    evaluation="Attempt the engine paths and record the human decision.",
    evidence_required="The refusals and the human decision record.",
    layer="deterministic",
)
def graph_protected(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    graph = module.DECISIONS.graph.create(state, nodes=[
        {"id": "gate", "kind": "HUMAN_GATE", "title": "release approval"},
    ], task_id="bench-S4B")
    start_message = ""
    try:
        module.DECISIONS.graph.mark_running(state, graph["graph_id"], "gate")
    except module.CONTRACTS.ContractError as exc:
        start_message = str(exc)
    satisfaction_message = ""
    try:
        module.DECISIONS.graph.mark_outcome(
            state, graph["graph_id"], "gate", status="SUCCEEDED", outcome={"approved": True},
            human_decision={"identity": "engine", "channel": "engine", "approved": True},
        )
    except module.CONTRACTS.ContractError as exc:
        satisfaction_message = str(exc)
    refused = module.DECISIONS.graph.record_human_decision(
        state, graph["graph_id"], "gate", identity="operator", approved=False, note="not yet",
    )
    problems = []
    if "human gate" not in start_message:
        problems.append(f"start message={start_message!r}")
    if not satisfaction_message:
        problems.append("an engine decision satisfied the human gate")
    if refused["status"] != "REFUSED" or refused["human_decision"]["approved"] is not False:
        problems.append(f"human decision={refused}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual="human gate refused engine action and recorded the human rejection",
        evidence={"start": start_message, "satisfaction": satisfaction_message, "refused": refused, "problems": problems},
        metrics={"model_calls": 0},
    )


# ================================================================= batching


@case(
    id="decision-batching.independent-questions-share-one-call",
    group="decision-batching",
    title="Independent questions over one projection share a single provider call",
    task="Evaluate two independent bounded questions that share a projection contract and state.",
    expectation="The provider is called once with both questions, and both answers map back by question id.",
    evaluation="Evaluate the step and read the provider call log and the mapped results.",
    evidence_required="The call log and the result rows.",
    layer="deterministic",
)
def batching_shared(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = deterministic(module, {
        "a": {"answer": "x", "confidence": 0.9, "confidence_kind": "DERIVED_CONFIDENCE"},
        "b": {"answer": "y", "confidence": 0.9, "confidence_kind": "DERIVED_CONFIDENCE"},
    })
    questions = [
        module.DECISIONS.contracts.DecisionQuestion(
            question_id="a", instructions="Choose a.", options=("x", "y"),
            projection_contract="failure-classification",
        ),
        module.DECISIONS.contracts.DecisionQuestion(
            question_id="b", instructions="Choose b.", options=("x", "y"),
            projection_contract="failure-classification",
        ),
    ]
    result = module.DECISIONS.planner.evaluate_step(
        state, questions=questions, projections={"failure-classification": failure_projection(module)},
        provider=provider, task_id="bench-S4B",
    )
    problems = []
    if len(provider.calls) != 1 or len(provider.calls[0]["questions"]) != 2:
        problems.append(f"calls={provider.calls}")
    if {row["question_id"] for row in result["results"]} != {"a", "b"}:
        problems.append(f"results={result['results']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"calls={len(provider.calls)} questions_per_call={len(provider.calls[0]['questions']) if provider.calls else 0}",
        evidence={"calls": provider.calls, "results": result["results"], "problems": problems},
        metrics={"model_calls": 1, "questions": 2},
    )


@case(
    id="decision-batching.dependent-question-is-staged",
    group="decision-batching",
    title="A dependent question waits for another step instead of sharing a call",
    task="Plan two questions where the second depends on the first answer.",
    expectation="The plan has two steps, the dependency edge is recorded, and each step is proven independent.",
    evaluation="Plan the steps and read the step list and the independence check.",
    evidence_required="The step plan and the dependency check result.",
    layer="deterministic",
)
def batching_dependent(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    questions = [
        module.DECISIONS.contracts.DecisionQuestion(
            question_id="a", instructions="Choose a.", options=("x", "y"),
            projection_contract="failure-classification",
        ),
        module.DECISIONS.contracts.DecisionQuestion(
            question_id="b", instructions="Choose b.", options=("x", "y"),
            projection_contract="failure-classification",
        ),
    ]
    plan = module.DECISIONS.planner.plan_steps(questions, depends_on={"b": ["a"]})
    problems = []
    if plan["steps"] != [["a"], ["b"]]:
        problems.append(f"steps={plan['steps']}")
    if plan["batches"] != 2:
        problems.append("dependent questions were not staged")
    in_step = module.ECONOMICS.batch_dependency_problems(
        [{"question_id": "a"}, {"question_id": "b"}], depends_on={"b": ["a"]},
    )
    if not in_step:
        problems.append("the AR-204 independence protection stopped refusing chained batches")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"steps={plan['steps']}",
        evidence={"plan": plan, "in_step_problems": in_step, "problems": problems},
        metrics={"model_calls": 0},
    )


@case(
    id="decision-batching.different-projections-split-cleanly",
    group="decision-batching",
    title="Questions that need different projections are separate calls",
    task="Evaluate one failure-classification question and one review-escalation question.",
    expectation="Two provider calls are made, one per projection group, and both answers map back.",
    evaluation="Evaluate the step and read the call log.",
    evidence_required="The call log with both question sets.",
    layer="deterministic",
)
def batching_projections(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = deterministic(module, {
        "failure-class": FAILURE_SCRIPT["failure-class"],
        "review-escalation": {"answer": "routine", "confidence": 0.9, "confidence_kind": "DERIVED_CONFIDENCE"},
    })
    questions = [
        classification_question(module),
        module.DECISIONS.contracts.DecisionQuestion(
            question_id="review-escalation", instructions="Choose the escalation.",
            options=module.CONTRACTS.REVIEW_ESCALATIONS,
            projection_contract="review-escalation",
        ),
    ]
    projections = {
        "failure-classification": failure_projection(module),
        "review-escalation": module.DECISIONS.projections.build(
            "review-escalation",
            entries={"stakes": "LOW", "affected_scope": [], "verification_result": "VERIFIED", "protected": False},
        ),
    }
    result = module.DECISIONS.planner.evaluate_step(
        state, questions=questions, projections=projections, provider=provider, task_id="bench-S4B",
    )
    problems = []
    if len(provider.calls) != 2:
        problems.append(f"calls={provider.calls}")
    if sorted(row["question_id"] for row in result["results"]) != ["failure-class", "review-escalation"]:
        problems.append(f"results={result['results']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"calls={len(provider.calls)} results={result['mapped']}",
        evidence={"calls": provider.calls, "problems": problems},
        metrics={"model_calls": 2, "questions": 2},
    )


@case(
    id="decision-batching.missing-answer-is-a-failure",
    group="decision-batching",
    title="A missing answer is recorded failed, never mapped to a nearby question",
    task="Evaluate two questions when the provider only answers one of them.",
    expectation="The answered question maps to its own answer and the unanswered one is failed; nothing is guessed.",
    evaluation="Evaluate the step and read each result row.",
    evidence_required="Both result rows and the decision records.",
    layer="deterministic",
)
def batching_mapping(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = deterministic(module, {
        "a": {"answer": "x", "confidence": 0.9, "confidence_kind": "DERIVED_CONFIDENCE"},
    })
    questions = [
        module.DECISIONS.contracts.DecisionQuestion(
            question_id="a", instructions="Choose a.", options=("x", "y"),
            projection_contract="failure-classification",
        ),
        module.DECISIONS.contracts.DecisionQuestion(
            question_id="b", instructions="Choose b.", options=("x", "y"),
            projection_contract="failure-classification",
        ),
    ]
    result = module.DECISIONS.planner.evaluate_step(
        state, questions=questions, projections={"failure-classification": failure_projection(module)},
        provider=provider, task_id="bench-S4B",
    )
    by_question = {row["question_id"]: row for row in result["results"]}
    problems = []
    if by_question["a"]["status"] != "answered" or by_question["a"]["answer"] != "x":
        problems.append(f"a={by_question['a']}")
    if by_question["b"]["status"] != "failed" or by_question["b"]["answer"]:
        problems.append(f"b={by_question['b']}")
    if result["missing"]:
        problems.append(f"missing={result['missing']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"a={by_question['a']['status']} b={by_question['b']['status']}",
        evidence={"results": result["results"], "problems": problems},
        metrics={"model_calls": 1, "questions": 2},
    )


# ==================================================================== cache


@case(
    id="decision-cache.hit-preserves-provenance",
    group="decision-cache",
    title="A cache hit serves the decision without a provider call and preserves provenance",
    task="Evaluate one bounded question twice against the same state, provider and model version.",
    expectation="The second evaluation makes no provider call, cites the original decision and keeps its confidence kind.",
    evaluation="Evaluate twice with a counting provider and compare the two decision records.",
    evidence_required="The two decision records and the provider call log after the first call.",
    layer="deterministic",
)
def cache_hit(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = deterministic(module, FAILURE_SCRIPT, model_version="2026.1")
    question = classification_question(module)
    projection = failure_projection(module)
    first = module.DECISIONS.planner.evaluate_step(
        state, questions=[question], projections={"failure-classification": projection},
        provider=provider, task_id="bench-S4B", cache_enabled=True,
    )
    provider.calls.clear()
    second = module.DECISIONS.planner.evaluate_step(
        state, questions=[question], projections={"failure-classification": projection},
        provider=provider, task_id="bench-S4B", cache_enabled=True,
    )
    first_record = module.DECISIONS.planner.decision(state, first["results"][0]["decision_id"])
    second_record = module.DECISIONS.planner.decision(state, second["results"][0]["decision_id"])
    problems = []
    if provider.calls:
        problems.append(f"the cache hit still called the provider: {provider.calls}")
    if second["results"][0]["cached"] is not True:
        problems.append("the reuse was not marked cached")
    if second_record["source_decision_id"] != first_record["decision_id"]:
        problems.append("the reuse does not cite the original decision")
    if (second_record["confidence"], second_record["confidence_kind"]) != (
        first_record["confidence"], first_record["confidence_kind"]
    ):
        problems.append("the reuse changed the confidence provenance")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"cached={second['results'][0]['cached']} calls_after_hit={len(provider.calls)}",
        evidence={"first": first_record, "reused": second_record, "problems": problems},
        metrics={"model_calls": 1, "cache_reuses": 1},
    )


@case(
    id="decision-cache.miss-on-state-change",
    group="decision-cache",
    title="A changed projected state misses the cache",
    task="Cache a decision, then look it up against a different projection digest.",
    expectation="The lookup misses with reason STATE_CHANGED and no cached answer is served.",
    evaluation="Look the decision up against changed evidence and read the miss reason.",
    evidence_required="The lookup result and the cache summary.",
    layer="deterministic",
)
def cache_state_miss(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = deterministic(module, FAILURE_SCRIPT, model_version="2026.1")
    question = classification_question(module)
    module.DECISIONS.planner.evaluate_step(
        state, questions=[question], projections={"failure-classification": failure_projection(module)},
        provider=provider, task_id="bench-S4B", cache_enabled=True,
    )
    changed = failure_projection(module, source="another-source", detail="different evidence")
    lookup = module.DECISIONS.cache.lookup(
        state, question=question, projection_digest=changed["digest"],
        provider="deterministic-fixture", model_version="2026.1",
    )
    problems = []
    if lookup["hit"] is not False or lookup["reason"] != "STATE_CHANGED":
        problems.append(f"lookup={lookup}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"hit={lookup['hit']} reason={lookup['reason']}",
        evidence={"lookup": {key: lookup[key] for key in ("hit", "reason", "detail")}, "problems": problems},
        metrics={"model_calls": 0, "cache_misses": 1},
    )


@case(
    id="decision-cache.miss-on-model-version-change",
    group="decision-cache",
    title="A model version change misses the cache",
    task="Cache a decision under one concrete model version, then look it up under another.",
    expectation="The lookup misses with reason MODEL_VERSION_CHANGED; a moving alias is refused outright.",
    evaluation="Look the decision up under a different version and attempt a cache key with an alias.",
    evidence_required="The miss reason and the alias refusal.",
    layer="deterministic",
)
def cache_model_miss(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = deterministic(module, FAILURE_SCRIPT, model_version="2026.1")
    question = classification_question(module)
    projection = failure_projection(module)
    module.DECISIONS.planner.evaluate_step(
        state, questions=[question], projections={"failure-classification": projection},
        provider=provider, task_id="bench-S4B", cache_enabled=True,
    )
    lookup = module.DECISIONS.cache.lookup(
        state, question=question, projection_digest=projection["digest"],
        provider="deterministic-fixture", model_version="2026.2",
    )
    alias_message = ""
    try:
        module.DECISIONS.cache.key_for(
            question, projection_digest=projection["digest"], provider="p",
            model_version="jev-latest", policy_version="v",
        )
    except module.CONTRACTS.ContractError as exc:
        alias_message = str(exc)
    problems = []
    if lookup["hit"] is not False or lookup["reason"] != "MODEL_VERSION_CHANGED":
        problems.append(f"lookup={lookup}")
    if "concrete model version" not in alias_message:
        problems.append(f"alias message={alias_message!r}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"reason={lookup['reason']} alias_refused={bool(alias_message)}",
        evidence={"lookup": {key: lookup[key] for key in ("hit", "reason")}, "alias": alias_message, "problems": problems},
        metrics={"model_calls": 0},
    )


@case(
    id="decision-cache.miss-on-question-version-change",
    group="decision-cache",
    title="A question definition change misses the cache",
    task="Cache a decision, then look it up with the same question id at a new definition version.",
    expectation="The lookup misses with reason QUESTION_DEFINITION_CHANGED.",
    evaluation="Change the definition version and read the miss reason.",
    evidence_required="The miss reason and the two definition digests.",
    layer="deterministic",
)
def cache_question_miss(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = deterministic(module, FAILURE_SCRIPT, model_version="2026.1")
    projection = failure_projection(module)
    module.DECISIONS.planner.evaluate_step(
        state, questions=[classification_question(module)], projections={"failure-classification": projection},
        provider=provider, task_id="bench-S4B", cache_enabled=True,
    )
    changed = classification_question(module, definition_version="2")
    lookup = module.DECISIONS.cache.lookup(
        state, question=changed, projection_digest=projection["digest"],
        provider="deterministic-fixture", model_version="2026.1",
    )
    problems = []
    if lookup["hit"] is not False or lookup["reason"] != "QUESTION_DEFINITION_CHANGED":
        problems.append(f"lookup={lookup}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"reason={lookup['reason']}",
        evidence={"lookup": {key: lookup[key] for key in ("hit", "reason")}, "problems": problems},
        metrics={"model_calls": 0},
    )


@case(
    id="decision-cache.stale-and-revoked-are-refused",
    group="decision-cache",
    title="A stale, expired or revoked entry is refused, never silently reused",
    task="Cache a decision with a TTL, expire it, and separately revoke another entry.",
    expectation="Expiry marks the entry STALE and the lookup refuses it; revocation refuses with reason REVOKED.",
    evaluation="Expire the cache, look up, revoke, and look up again.",
    evidence_required="The two refusal reasons and the entry freshness.",
    layer="deterministic",
)
def cache_stale(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = deterministic(module, FAILURE_SCRIPT, model_version="2026.1")
    question = classification_question(module)
    projection = failure_projection(module)
    module.DECISIONS.planner.evaluate_step(
        state, questions=[question], projections={"failure-classification": projection},
        provider=provider, task_id="bench-S4B", cache_enabled=True, cache_ttl_seconds=60,
    )
    from datetime import datetime, timedelta, timezone
    expired = module.DECISIONS.cache.expire(state, now=datetime.now(timezone.utc) + timedelta(seconds=120))
    stale_lookup = module.DECISIONS.cache.lookup(
        state, question=question, projection_digest=projection["digest"],
        provider="deterministic-fixture", model_version="2026.1",
    )
    module.DECISIONS.cache.invalidate(
        state, question_id="failure-class", reason="the question was reformulated",
    )
    revoked_lookup = module.DECISIONS.cache.lookup(
        state, question=question, projection_digest=projection["digest"],
        provider="deterministic-fixture", model_version="2026.1",
    )
    problems = []
    if not expired or stale_lookup["hit"] is not False:
        problems.append(f"expiry did not refuse the entry: {stale_lookup}")
    if revoked_lookup["hit"] is not False or revoked_lookup["reason"] != "REVOKED":
        problems.append(f"revocation did not refuse the entry: {revoked_lookup}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"expired={len(expired)} stale_reason={stale_lookup['reason']} revoked_reason={revoked_lookup['reason']}",
        evidence={"stale": stale_lookup, "revoked": revoked_lookup, "problems": problems},
        metrics={"model_calls": 0},
    )


# ================================================================ escalation


@case(
    id="decision-escalation.accepted-decision-stops",
    group="decision-escalation",
    title="An accepted decision stops the escalation ladder",
    task="Evaluate a low-consequence question that the provider answers with derived confidence.",
    expectation="The decision is answered, policy accepts it, and the escalation verdict does not escalate.",
    evaluation="Evaluate the question and read the escalation verdict.",
    evidence_required="The decision record and its escalation verdict.",
    layer="deterministic",
)
def escalation_stops(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    result = module.DECISIONS.integrations.classify_failure(
        state, source="mystery", provider=deterministic(module, FAILURE_SCRIPT), task_id="bench-S4B",
    )
    record = module.DECISIONS.batch.decision(state, result["decision_id"])
    verdict = module.DECISIONS.escalation.escalation_for(
        record, classification="BOUNDED", consequence="LOW",
    )
    problems = []
    if result["class"] != "IMPLEMENTATION_FAILURE" or result["source"] != "bounded-decision":
        problems.append(f"result={result['class']}/{result['source']}")
    if verdict["escalated"] is not False or verdict["next"]:
        problems.append(f"verdict={verdict}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"class={result['class']} escalated={verdict['escalated']}",
        evidence={"record": record, "verdict": verdict, "problems": problems},
        metrics={"model_calls": 1},
    )


@case(
    id="decision-escalation.low-confidence-escalates",
    group="decision-escalation",
    title="Low or missing confidence escalates with a structured reason",
    task="Refuse a medium-consequence judgement that only carries self-reported confidence, and one with none.",
    expectation="The verdicts carry LOW_CONFIDENCE and NO_CONFIDENCE, and neither becomes a silent retry.",
    evaluation="Evaluate both questions and read their escalation verdicts.",
    evidence_required="Both decision records and verdicts.",
    layer="deterministic",
)
def escalation_low_confidence(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    projection = failure_projection(module)
    weak = deterministic(module, {
        "failure-class": {"answer": "TIMEOUT", "confidence": 0.4,
                          "confidence_kind": "SELF_REPORTED_CONFIDENCE"},
    })
    result = module.DECISIONS.planner.evaluate_step(
        state,
        questions=[classification_question(module, consequence="MEDIUM")],
        projections={"failure-classification": projection}, provider=weak, task_id="bench-S4B",
    )
    record = module.DECISIONS.planner.decision(state, result["results"][0]["decision_id"])
    low = module.DECISIONS.escalation.escalation_for(
        record, classification="BOUNDED", consequence="MEDIUM",
    )
    silent = deterministic(module, {"failure-class": {"answer": "TIMEOUT"}})
    result_none = module.DECISIONS.planner.evaluate_step(
        state,
        questions=[classification_question(module, consequence="MEDIUM")],
        projections={"failure-classification": projection}, provider=silent, task_id="bench-S4B",
        cache_enabled=False,
    )
    record_none = module.DECISIONS.planner.decision(state, result_none["results"][0]["decision_id"])
    none = module.DECISIONS.escalation.escalation_for(
        record_none, classification="BOUNDED", consequence="MEDIUM",
    )
    problems = []
    if low["reason"] != "LOW_CONFIDENCE" or low["next"] not in ("STRONGER_BOUNDED", "GENERATIVE", "HUMAN"):
        problems.append(f"low={low}")
    if none["reason"] != "NO_CONFIDENCE":
        problems.append(f"none={none}")
    if low["reason"] == "LOW_CONFIDENCE" and low["escalated"] is not True:
        problems.append("a low-confidence verdict did not escalate")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"low={low['reason']} none={none['reason']}",
        evidence={"low": low, "none": none, "problems": problems},
        metrics={"model_calls": 2},
    )


@case(
    id="decision-escalation.provider-unavailable-falls-back",
    group="decision-escalation",
    title="An unavailable provider falls back to UNKNOWN and escalates, never crashing",
    task="Ask an unmapped failure classification with no provider configured.",
    expectation="The class stays UNKNOWN, the source is fallback-unknown, the decision is recorded as unavailable and the caller is told to escalate.",
    evaluation="Call the integration with the default provider and read the result and decision record.",
    evidence_required="The result, the decision record status and the escalation reason.",
    layer="deterministic",
)
def escalation_unavailable(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    result = module.EXECUTION.classify_with_decision(state, source="mystery-source", task_id="bench-S4B")
    record = module.DECISIONS.batch.decision(state, result["decision_id"]) if result["decision_id"] else None
    problems = []
    if result["class"] != "UNKNOWN" or result["source"] != "fallback-unknown":
        problems.append(f"result={result['class']}/{result['source']}")
    if not result["escalation_required"]:
        problems.append("the fallback did not escalate")
    if record is None or record["status"] != "unavailable":
        problems.append(f"record={(record or {}).get('status')}")
    escalation_reason = (result.get("escalation") or {}).get("reason", "")
    if escalation_reason != "NO_DECISION_PROVIDER":
        problems.append(f"escalation={result.get('escalation')}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"class={result['class']} source={result['source']} escalation={escalation_reason}",
        evidence={"result": result, "problems": problems},
        metrics={"model_calls": 0},
    )


@case(
    id="decision-escalation.human-policy-wins-over-confidence",
    group="decision-escalation",
    title="A protected operation reaches the human rung regardless of confidence",
    task="Ask for an escalation verdict on a protected operation with a 0.99 calibrated answer.",
    expectation="The verdict is POLICY_REQUIRES_HUMAN and the ladder lands on HUMAN.",
    evaluation="Build the record and read the verdict.",
    evidence_required="The escalation verdict.",
    layer="deterministic",
)
def escalation_human(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    record = {
        "decision_id": "dec_fixture_00000000",
        "status": "answered",
        "answer_valid": True,
        "confidence": 0.99,
        "confidence_kind": "CALIBRATED_PROBABILITY",
        "policy_verdict": {"accepted": True},
    }
    verdict = module.DECISIONS.escalation.escalation_for(
        record, classification="BOUNDED", consequence="PROTECTED",
    )
    policy = module.DECISIONS.policy.may_act(record, consequence="PROTECTED")
    problems = []
    if verdict["reason"] != "POLICY_REQUIRES_HUMAN" or verdict["next"] != "HUMAN":
        problems.append(f"verdict={verdict}")
    if policy["accepted"] is not False:
        problems.append("confidence authorized a protected operation")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"verdict={verdict['reason']}->{verdict['next']} policy_accepted={policy['accepted']}",
        evidence={"verdict": verdict, "policy": policy, "problems": problems},
        metrics={"model_calls": 0},
    )


@case(
    id="decision-escalation.stronger-is-not-more-expensive",
    group="decision-escalation",
    title="Stronger options are capability-shaped, never price-ranked",
    task="List the strengthening options for a refused decision.",
    expectation="Options name capability mechanisms and carry no price or cost ordering.",
    evaluation="Read the stronger options and check their vocabulary.",
    evidence_required="The option list.",
    layer="deterministic",
)
def escalation_options(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    options = module.DECISIONS.escalation.stronger_options(
        record={"status": "refused"}, alternate_providers_available=True,
        richer_projection_available=True, alternate_definition_available=True,
    )
    names = {option["option"] for option in options}
    problems = []
    if not {"alternate_provider", "richer_projection", "alternate_question_version",
            "independent_second_decision"} <= names:
        problems.append(f"options={names}")
    for option in options:
        text = f"{option.get('option')} {option.get('detail')}".lower()
        if "price" in text or "cheap" in text or "cost" in text:
            problems.append(f"an option is price-shaped: {option}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"options={len(options)}",
        evidence={"options": options, "problems": problems},
        metrics={"model_calls": 0},
    )


# ============================================================== integrations


@case(
    id="decision-integrations.failure-classification-code-first",
    group="decision-integrations",
    title="The failure integration never consults a provider for a mapped source",
    task="Classify a source the declared vocabulary already maps, with a counting provider configured.",
    expectation="The deterministic class is returned, the source is deterministic and the provider is not called.",
    evaluation="Call the integration with a counting provider and read its call log.",
    evidence_required="The result and the empty provider call log.",
    layer="deterministic",
)
def integration_failure_first(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    counting = deterministic(module, FAILURE_SCRIPT)
    result = module.EXECUTION.classify_with_decision(
        state, source="routine", provider=counting, task_id="bench-S4B",
    )
    problems = []
    if result["source"] != "deterministic":
        problems.append(f"source={result['source']}")
    if counting.calls:
        problems.append(f"the provider was called for a mapped source: {counting.calls}")
    if result["class"] != "IMPLEMENTATION_FAILURE":
        problems.append(f"class={result['class']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"class={result['class']} source={result['source']} calls={len(counting.calls)}",
        evidence={"result": result, "calls": counting.calls, "problems": problems},
        metrics={"model_calls": 0},
    )


@case(
    id="decision-integrations.review-escalation-policy-stays-deterministic",
    group="decision-integrations",
    title="Review escalation advice never replaces the review policy",
    task="Ask for review advice deterministically and through a bounded question.",
    expectation="Deterministic rules answer where they can; a bounded answer records policy_still_controls and no provider call is wasted.",
    evaluation="Call the advice twice and read the results and call log.",
    evidence_required="Both advice results and the provider call log.",
    layer="deterministic",
)
def integration_review(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    counting = deterministic(module, {
        "review-escalation": {"answer": "enhanced_review", "confidence": 0.9,
                              "confidence_kind": "DERIVED_CONFIDENCE"},
    })
    deterministic_advice = module.REVIEWS.escalation_advice(
        state, stakes="LOW", verification_result="INDEPENDENTLY_REPRODUCED", provider=counting,
    )
    bounded_advice = module.REVIEWS.escalation_advice(
        state, stakes="MEDIUM", verification_result="UNVERIFIED", provider=counting,
        task_id="bench-S4B", verification_level="OBSERVED",
    )
    protected = module.REVIEWS.escalation_advice(
        state, stakes="HIGH", verification_result="UNVERIFIED", protected=True, provider=counting,
    )
    problems = []
    if deterministic_advice["escalation"] != "routine" or deterministic_advice["source"] != "deterministic":
        problems.append(f"deterministic advice={deterministic_advice}")
    if bounded_advice["escalation"] != "enhanced_review" or bounded_advice["source"] != "bounded-decision":
        problems.append(f"bounded advice={bounded_advice}")
    if bounded_advice["policy_still_controls"] is not True:
        problems.append("the advice claims policy authority")
    if protected["escalation"] != "human_attention":
        problems.append(f"protected advice={protected}")
    if len(counting.calls) != 1:
        problems.append(f"calls={counting.calls}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"deterministic={deterministic_advice['escalation']} bounded={bounded_advice['escalation']}",
        evidence={
            "deterministic": deterministic_advice, "bounded": bounded_advice,
            "protected": protected, "calls": counting.calls, "problems": problems,
        },
        metrics={"model_calls": 1},
    )


@case(
    id="decision-integrations.evidence-relevance-cannot-elevate-stale",
    group="decision-integrations",
    title="Evidence relevance never overrides freshness or provenance",
    task="Ask about stale evidence, evidence without provenance, and fresh evidence, with a provider that would always say SUPPORTS.",
    expectation="Stale answers IRRELEVANT and provenance-free answers UNKNOWN deterministically; only the fresh claim reaches the provider.",
    evaluation="Call the integration three times and read the answers and call log.",
    evidence_required="The three answers and the provider call log.",
    layer="deterministic",
)
def integration_relevance(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = deterministic(module, {
        "evidence-relevance": {"answer": "SUPPORTS", "confidence": 0.99,
                               "confidence_kind": "CALIBRATED_PROBABILITY"},
    })
    stale = module.VERIFICATION.relevance_advice(
        state, requirement="req", claim="claim", provenance={"source": "x"},
        freshness="STALE", provider=provider,
    )
    unproven = module.VERIFICATION.relevance_advice(
        state, requirement="req", claim="claim", provenance="", freshness="CURRENT", provider=provider,
    )
    fresh = module.VERIFICATION.relevance_advice(
        state, requirement="req", claim="claim", provenance={"source": "x"},
        freshness="CURRENT", provider=provider, task_id="bench-S4B",
    )
    problems = []
    if stale["answer"] != "IRRELEVANT" or stale["source"] != "deterministic":
        problems.append(f"stale={stale}")
    if unproven["answer"] != "UNKNOWN" or unproven["source"] != "deterministic":
        problems.append(f"unproven={unproven}")
    if fresh["answer"] != "SUPPORTS" or fresh["source"] != "bounded-decision":
        problems.append(f"fresh={fresh}")
    if len(provider.calls) != 1:
        problems.append(f"calls={provider.calls}")
    if stale["may_override_freshness"] is not False:
        problems.append("the stale guard claims it may be overridden")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"stale={stale['answer']} unproven={unproven['answer']} fresh={fresh['answer']}",
        evidence={"stale": stale, "unproven": unproven, "fresh": fresh, "problems": problems},
        metrics={"model_calls": 1},
    )


@case(
    id="decision-integrations.route-family-deterministic-first",
    group="decision-integrations",
    title="Routing advice resolves known structure deterministically and protects human policy",
    task="Ask for a route family for a declared implementation kind, an unknown kind, and a protected operation.",
    expectation="Declared kinds resolve without a call, an unknown kind may be bounded, and a protected operation stays unknown with policy authority.",
    evaluation="Call the advice three times and read the families and call log.",
    evidence_required="The three advice results and the call log.",
    layer="deterministic",
)
def integration_route(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = deterministic(module, {
        "route-family": {"answer": "research", "confidence": 0.9, "confidence_kind": "DERIVED_CONFIDENCE"},
    })
    known = module.ROUTING.family_advice(state, task_kind="implementation", provider=provider)
    unknown = module.ROUTING.family_advice(
        state, task_kind="something-new", difficulty="MEDIUM", stakes="LOW",
        available_capabilities=["core"], required_capabilities=["core"], provider=provider,
        task_id="bench-S4B",
    )
    protected = module.ROUTING.family_advice(state, task_kind="something-new", protected=True, provider=provider)
    problems = []
    if known["family"] != "implementation" or known["source"] != "deterministic":
        problems.append(f"known={known}")
    if unknown["family"] != "research" or unknown["source"] != "bounded-decision":
        problems.append(f"unknown={unknown}")
    if protected["family"] != "unknown" or protected["policy_authority"] != "deterministic":
        problems.append(f"protected={protected}")
    if len(provider.calls) != 1:
        problems.append(f"calls={provider.calls}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"known={known['family']} unknown={unknown['family']} protected={protected['family']}",
        evidence={"known": known, "unknown": unknown, "protected": protected, "problems": problems},
        metrics={"model_calls": 1},
    )


# ================================================================ economics


@case(
    id="decision-economics.structural-counts-come-from-records",
    group="decision-economics",
    title="Decision economics count calls, avoidance and cache reuse from records",
    task="Compile a mixed plan, resolve a bounded question, reuse it, and read the economics.",
    expectation="Avoided deterministic calls, provider calls, cache reuses and questions per batch are all reported without fabricated money.",
    evaluation="Run the flow and read the intelligence economics.",
    evidence_required="The economics view and the underlying records.",
    layer="deterministic",
)
def economics_counts(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = deterministic(module, FAILURE_SCRIPT, model_version="2026.1")
    plan = module.DECISIONS.compiler.compile_plan(
        state,
        requirements=[
            {"requirement_id": "test", "kind": "test-exit-code", "known": True, "value": 1},
            {"requirement_id": "failure-class", "kind": "failure-class"},
        ],
        task_id="bench-S4B", decision_provider=provider,
    )
    projection = failure_projection(module)
    question = classification_question(module)
    module.DECISIONS.planner.evaluate_step(
        state, questions=[question], projections={"failure-classification": projection},
        provider=provider, task_id="bench-S4B", cache_enabled=True,
    )
    module.DECISIONS.planner.evaluate_step(
        state, questions=[question], projections={"failure-classification": projection},
        provider=provider, task_id="bench-S4B", cache_enabled=True,
    )
    view = module.DECISIONS.economics.intelligence_economics(state, task_id="bench-S4B")
    problems = []
    if view["counts"]["model_calls_avoided_by_deterministic"] != 1:
        problems.append(f"avoided={view['counts']}")
    if view["provider_calls"] != 1:
        problems.append(f"provider_calls={view['provider_calls']}")
    if view["cache_reuses"] != 1:
        problems.append(f"cache_reuses={view['cache_reuses']}")
    if view["questions_per_batch"] != [1]:
        problems.append(f"questions_per_batch={view['questions_per_batch']}")
    if "no monetary saving" not in view["note"]:
        problems.append("the economics claim a monetary saving")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"calls={view['provider_calls']} reuses={view['cache_reuses']} avoided={view['counts']['model_calls_avoided_by_deterministic']}",
        evidence={"intelligence": view, "plan": plan["plan_id"], "problems": problems},
        metrics={"model_calls": 1, "cache_reuses": 1},
    )


@case(
    id="decision-economics.compiled-plan-comparison-is-structural",
    group="decision-economics",
    title="The compiled-plan comparison is structural and claims no quality parity",
    task="Compare an old execution plan with the decision-compiled plan for a compiled task.",
    expectation="Model calls, decision calls, state bytes, stages and workers are reported with explicit deltas and a claim boundary.",
    evaluation="Build the comparison and read the deltas and boundary.",
    evidence_required="The comparison document.",
    layer="deterministic",
)
def economics_comparison(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = deterministic(module, FAILURE_SCRIPT, model_version="2026.1")
    module.DECISIONS.compiler.compile_plan(
        state,
        requirements=[{"requirement_id": "failure-class", "kind": "failure-class"}],
        task_id="bench-S4B", decision_provider=provider,
    )
    module.DECISIONS.planner.evaluate_step(
        state, questions=[classification_question(module)],
        projections={"failure-classification": failure_projection(module)},
        provider=provider, task_id="bench-S4B",
    )
    comparison = module.DECISIONS.economics.compiled_plan_comparison(
        state,
        baseline={"model_calls": 3, "decision_calls": 0, "state_bytes": 12_000,
                  "generative_stages": 2, "verification_stages": 1, "worker_count": 2},
        task_id="bench-S4B",
    )
    problems = []
    if comparison["compiled"]["model_calls"] != 1:
        problems.append(f"compiled={comparison['compiled']}")
    if comparison["deltas"]["model_calls"] != -2:
        problems.append(f"deltas={comparison['deltas']}")
    if "no quality parity is claimed" not in comparison["claim_boundary"]:
        problems.append("the comparison claims quality parity")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"compiled_model_calls={comparison['compiled']['model_calls']} delta={comparison['deltas']['model_calls']}",
        evidence={"comparison": comparison, "problems": problems},
        metrics={"model_calls": 1},
    )


@case(
    id="decision-economics.generation-avoidance-is-counted",
    group="decision-economics",
    title="Bounded decisions are counted as avoided generative calls, structurally",
    task="Compile a plan with a bounded question and read the avoidance counts.",
    expectation="The bounded question is counted once as an avoided generative call and no monetary figure is produced.",
    evaluation="Compile the plan and read its economics block.",
    evidence_required="The plan economics block.",
    layer="deterministic",
)
def economics_avoidance(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    plan = module.DECISIONS.compiler.compile_plan(
        state,
        requirements=[{"requirement_id": "failure-class", "kind": "failure-class"}],
        task_id="bench-S4B", decision_provider=deterministic(module, FAILURE_SCRIPT),
    )
    economics = plan["economics"]
    problems = []
    if economics["model_calls_avoided_by_bounded_decision"] != 1:
        problems.append(f"economics={economics}")
    if economics["generative_calls_required"] != 0:
        problems.append("a bounded question required generation")
    if "no monetary saving" not in economics["note"]:
        problems.append("the plan economics claim money")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"avoided_by_bounded={economics['model_calls_avoided_by_bounded_decision']}",
        evidence={"economics": economics, "problems": problems},
        metrics={"model_calls": 0},
    )


# ============================================================ golden workflows


@case(
    id="golden-workflows.d1-code-knows",
    group="golden-workflows",
    title="D1: an exact fact never becomes a decision or a model call",
    task="Compile and resolve a task whose only requirement code can establish exactly.",
    expectation="No bounded question, no provider call, no generation; the fast path applies.",
    evaluation="Compile the plan, run the deterministic integration path and read every counter.",
    evidence_required="The plan, the provider call log and the fast-path verdict.",
    layer="deterministic",
)
def golden_d1(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    counting = deterministic(module, FAILURE_SCRIPT)
    plan = module.DECISIONS.compiler.compile_plan(
        state,
        requirements=[{"requirement_id": "test", "kind": "test-exit-code", "known": True, "value": 0,
                       "statement": "npm test exited 0"}],
        task_id="bench-S4B", decision_provider=counting, deterministic_verification=True,
    )
    result = module.EXECUTION.classify_with_decision(
        state, source="routine", provider=counting, task_id="bench-S4B",
    )
    problems = []
    if plan["bounded_questions"] or plan["generative_needs"]:
        problems.append("a deterministic task produced a question or a generative need")
    if not plan["fast_path"]["applies"]:
        problems.append("the fast path did not apply")
    if counting.calls:
        problems.append(f"a model was consulted: {counting.calls}")
    if result["source"] != "deterministic":
        problems.append(f"classification source={result['source']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"questions=0 calls={len(counting.calls)} fast_path={plan['fast_path']['applies']}",
        evidence={"plan": plan, "classification": result, "calls": counting.calls, "problems": problems},
        metrics={"model_calls": 0},
    )


@case(
    id="golden-workflows.d2-bounded-judgment-drives-one-repair",
    group="golden-workflows",
    title="D2: an ambiguous failure becomes one bounded judgement, one repair, one verification",
    task="Classify an unmapped failure with a deterministic provider, act on the accepted class, and record the verification.",
    expectation="A ChoiceDecision produces the class, policy accepts it, the action cites the decision and the verification follows it in the trace.",
    evaluation="Run the flow and read the decision, the action edge, the verification and the trace.",
    evidence_required="The decision record, the action fields, the verification record and the trace steps.",
    layer="deterministic",
)
def golden_d2(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = deterministic(module, FAILURE_SCRIPT, model_version="2026.1")
    result = module.EXECUTION.classify_with_decision(
        state, source="mystery-source", detail="the command never returned",
        provider=provider, task_id="bench-S4B",
    )
    module.DECISIONS.batch.mark_acted_on(
        state, result["decision_id"], action="repair-2",
    )
    verification = module.VERIFICATION.create(
        state, subject="repair-2", claim="the repair closed the bounded failure",
        level="DECLARED", method="engine-recorded", task_id="bench-S4B",
        evidence=["the repair-2 execution completed with a validated result"],
    )
    module.DECISIONS.batch.mark_acted_on(
        state, result["decision_id"], action="repair-2",
        verification_id=verification["verification_id"],
    )
    record = module.DECISIONS.batch.decision(state, result["decision_id"])
    explained = module.DECISIONS.trace.explain(state, task_id="bench-S4B")
    kinds = {step["kind"] for step in explained["trace"]["steps"]}
    problems = []
    if result["class"] != "IMPLEMENTATION_FAILURE" or result["source"] != "bounded-decision":
        problems.append(f"result={result['class']}/{result['source']}")
    if record["resulting_action"] != "repair-2":
        problems.append(f"action={record['resulting_action']!r}")
    if record["verification_id"] != verification["verification_id"]:
        problems.append("the verification is not bound to the decision")
    if not {"DECISION", "ACTION", "VERIFICATION"} <= kinds:
        problems.append(f"trace kinds={kinds}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"class={result['class']} action={record['resulting_action']} verification={verification['level']}",
        evidence={
            "decision": record, "verification": verification,
            "trace_kinds": sorted(kinds), "lines": explained["lines"], "problems": problems,
        },
        metrics={"model_calls": 1, "verifications": 1},
    )


@case(
    id="golden-workflows.d3-escalation-does-not-disguise-uncertainty",
    group="golden-workflows",
    title="D3: a low-confidence bounded decision escalates to a stronger path",
    task="Ask a medium-consequence question answered with self-reported confidence, then list the stronger options.",
    expectation="Policy refuses it, the ladder names LOW_CONFIDENCE and a stronger mechanism, and the options are capability-shaped.",
    evaluation="Run the flow and read the refusal, the escalation verdict and the options.",
    evidence_required="The refused decision, the escalation verdict and the stronger options.",
    layer="deterministic",
)
def golden_d3(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = deterministic(module, {
        "failure-class": {"answer": "TIMEOUT", "confidence": 0.4,
                          "confidence_kind": "SELF_REPORTED_CONFIDENCE"},
    }, model_version="2026.1")
    result = module.DECISIONS.planner.evaluate_step(
        state, questions=[classification_question(module, consequence="MEDIUM")],
        projections={"failure-classification": failure_projection(module)},
        provider=provider, task_id="bench-S4B", cache_enabled=False,
    )
    record = module.DECISIONS.planner.decision(state, result["results"][0]["decision_id"])
    verdict = module.DECISIONS.escalation.escalation_for(
        record, classification="BOUNDED", consequence="MEDIUM", stronger_available=True,
    )
    options = module.DECISIONS.escalation.stronger_options(
        record=record, alternate_providers_available=True, richer_projection_available=True,
    )
    problems = []
    if record["status"] != "refused":
        problems.append(f"status={record['status']}")
    if verdict["reason"] != "LOW_CONFIDENCE" or verdict["next"] != "STRONGER_BOUNDED":
        problems.append(f"verdict={verdict}")
    if not options:
        problems.append("no stronger path was offered")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"status={record['status']} escalation={verdict['reason']}->{verdict['next']} options={len(options)}",
        evidence={"decision": record, "verdict": verdict, "options": options, "problems": problems},
        metrics={"model_calls": 1, "escalations": 1},
    )


@case(
    id="golden-workflows.d4-high-confidence-still-stops-at-human",
    group="golden-workflows",
    title="D4: a high-confidence decision on a protected operation still needs the human gate",
    task="Answer a protected operation question with 0.99 calibrated confidence and run the graph to its human gate.",
    expectation="Policy refuses to authorize, the escalation lands on HUMAN, and the graph awaits rather than completing.",
    evaluation="Compile the protected task, evaluate the would-be decision, build the graph and read the boundary.",
    evidence_required="The policy verdict, the escalation verdict and the graph boundary.",
    layer="deterministic",
)
def golden_d4(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    confident = {
        "decision_id": "dec_fixture_00000000", "status": "answered", "answer_valid": True,
        "confidence": 0.99, "confidence_kind": "CALIBRATED_PROBABILITY",
        "policy_verdict": {"accepted": True}, "authorization_effect": "none",
    }
    policy = module.DECISIONS.policy.may_act(confident, consequence="PROTECTED")
    verdict = module.DECISIONS.escalation.escalation_for(
        confident, classification="BOUNDED", consequence="PROTECTED",
    )
    plan = module.DECISIONS.compiler.compile_plan(
        state, requirements=[{"requirement_id": "ship", "kind": "release-approval"}],
        task_id="bench-S4B", decision_provider=deterministic(module, FAILURE_SCRIPT),
    )
    graph = module.DECISIONS.graph.from_plan(state, plan)
    progress = module.DECISIONS.graph.progress(graph)
    problems = []
    if policy["accepted"] is not False or policy["authorization_effect"] != "none":
        problems.append(f"policy={policy}")
    if verdict["next"] != "HUMAN":
        problems.append(f"verdict={verdict}")
    if progress["success"] is True:
        problems.append("the graph reported success before the human gate")
    if not any(node["kind"] == "HUMAN_GATE" for node in graph["nodes"]):
        problems.append("no human gate node exists")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"policy_accepted={policy['accepted']} escalation={verdict['next']} graph_success={progress['success']}",
        evidence={"policy": policy, "verdict": verdict, "graph": graph, "problems": problems},
        metrics={"model_calls": 0},
    )


@case(
    id="golden-workflows.d5-cache-invalidation-on-relevant-change",
    group="golden-workflows",
    title="D5: a cached decision is reused only while the state is identical",
    task="Answer a question, reuse it, change the relevant evidence, and separately revoke it.",
    expectation="The identical state reuses without a call; a relevant state change misses; a revocation refuses.",
    evaluation="Run the flow and read the two decision ids, the miss reason and the revocation reason.",
    evidence_required="The reuse record, the miss reason and the revocation reason.",
    layer="deterministic",
)
def golden_d5(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = deterministic(module, FAILURE_SCRIPT, model_version="2026.1")
    question = classification_question(module)
    first_projection = failure_projection(module)
    first = module.DECISIONS.planner.evaluate_step(
        state, questions=[question], projections={"failure-classification": first_projection},
        provider=provider, task_id="bench-S4B", cache_enabled=True,
    )
    provider.calls.clear()
    reused = module.DECISIONS.planner.evaluate_step(
        state, questions=[question], projections={"failure-classification": first_projection},
        provider=provider, task_id="bench-S4B", cache_enabled=True,
    )
    changed_projection = failure_projection(module, source="changed-source", detail="new evidence")
    miss = module.DECISIONS.cache.lookup(
        state, question=question, projection_digest=changed_projection["digest"],
        provider="deterministic-fixture", model_version="2026.1",
    )
    module.DECISIONS.cache.invalidate(state, question_id="failure-class", reason="the requirement changed")
    revoked = module.DECISIONS.cache.lookup(
        state, question=question, projection_digest=first_projection["digest"],
        provider="deterministic-fixture", model_version="2026.1",
    )
    first_record = module.DECISIONS.planner.decision(state, first["results"][0]["decision_id"])
    reuse_record = module.DECISIONS.planner.decision(state, reused["results"][0]["decision_id"])
    problems = []
    if provider.calls or reused["results"][0]["cached"] is not True:
        problems.append("the identical state was not served from the cache")
    if reuse_record["source_decision_id"] != first_record["decision_id"]:
        problems.append("the reuse does not cite the original")
    if miss["hit"] is not False or miss["reason"] != "STATE_CHANGED":
        problems.append(f"miss={miss}")
    if revoked["hit"] is not False or revoked["reason"] != "REVOKED":
        problems.append(f"revoked={revoked}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"reused={reused['results'][0]['cached']} miss={miss['reason']} revoked={revoked['reason']}",
        evidence={
            "first": first_record, "reuse": reuse_record,
            "miss": {key: miss[key] for key in ("hit", "reason")},
            "revoked": {key: revoked[key] for key in ("hit", "reason")},
            "problems": problems,
        },
        metrics={"model_calls": 1, "cache_reuses": 1, "cache_misses": 2},
    )
