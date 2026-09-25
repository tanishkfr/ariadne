"""AR-203 deterministic benchmark cases: verification hardening and the decision plane.

Every case is offline, deterministic and dependency-free. They test whether a
claim can be *established from evidence that actually exists* — not whether a
model agrees, and not whether a workflow merely completes. The false-acceptance
group deliberately fabricates plausible success and requires it to fail.

The cases drive the engine modules directly through the runtime module
(``ctx.repo.module("ariadne.py")``), which is the same engine the CLI and the API
use; nothing here re-implements an engine rule.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

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
        "run_id": "bench-ar203",
        "project": str(box.project),
        "run_root": str(box.run_root),
        "packets": [{"id": "bench-S4B", "stage": "S4B", "path": str(box.run_root / "bench-S4B")}],
        "approvals": [],
    }
    state.update(extra)
    return state


def make_execution(module, state, *, role="implementer", adapter="fixture:worker",
                   revision=REVISION, requested=None, start=True):
    record = module.EXECUTION.create(
        state, task_id="bench-S4B", role=role, adapter=adapter,
        requested=requested or {"provider": "deepseek", "model": "deepseek-x", "worker_role": "bulk"},
        revision={"revision_hash": revision},
    )
    if start:
        module.EXECUTION.mark_started(state, record["execution_id"])
    return record


def evidence_file(box, name: str, text: str) -> Path:
    path = box.root / name
    path.write_text(text, encoding="utf-8")
    return path


# =========================================================== execution provenance


@case(
    id="execution-provenance.requested-and-observed-stay-distinct",
    group="execution-provenance",
    title="A requested model identity never becomes an observed one",
    task="Create an execution that requests a model and observe what identity the engine will report.",
    expectation="Requested identity is recorded at REQUESTED; observed identity stays UNKNOWN.",
    evaluation="Create the execution and read the per-field claim levels.",
    evidence_required="The claim map and the raw observed fields.",
    layer="deterministic",
)
def provenance_requested_vs_observed(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    record = make_execution(module, state)
    claims = module.PROVENANCE.identity_claims(record)
    problems = []
    if claims["model"]["level"] != "REQUESTED" or claims["model"]["value"] != "deepseek-x":
        problems.append(f"model claim={claims['model']}")
    if record["observed"]["model"] != "UNKNOWN" or record["observed"]["provider"] != "UNKNOWN":
        problems.append(f"observed={record['observed']}")
    if claims["provider"]["level"] != "REQUESTED":
        problems.append(f"provider claim={claims['provider']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"model={claims['model']['value']}/{claims['model']['level']} observed={record['observed']['model']}",
        evidence={"claims": claims, "observed": record["observed"], "problems": problems},
    )


@case(
    id="execution-provenance.worker-prose-cannot-replace-observed",
    group="execution-provenance",
    title="A worker's runtime claim never overwrites engine observation",
    task="Have the worker report a different model and attempt to write a provider observation.",
    expectation="The worker claim stays declared/reported, the observed channel stays UNKNOWN and the provider channel refuses worker sources.",
    evaluation="Report the claim, attempt the provider observation and read both refusals and the claim map.",
    evidence_required="The refusal, the claim map and the observed fields.",
    layer="deterministic",
)
def provenance_worker_prose(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    record = make_execution(module, state)
    module.EXECUTION.report(state, record["execution_id"], provider="openai", model="gpt-x", evidence="self")
    refusal = ""
    try:
        module.PROVENANCE.record_provider_observation(
            state, record["execution_id"], provider="openai", model="gpt-x", source="worker-output",
        )
    except module.CONTRACTS.ContractError as exc:
        refusal = str(exc)
    claims = module.PROVENANCE.identity_claims(record)
    view = module.EXECUTION.identity_view(state, record["execution_id"])
    problems = []
    if "worker output" not in refusal:
        problems.append(f"the provider channel accepted a worker source: {refusal!r}")
    if claims["model"]["level"] not in ("REQUESTED", "DECLARED"):
        problems.append(f"worker prose raised the claim level: {claims['model']}")
    if record["observed"]["model"] != "UNKNOWN":
        problems.append(f"observed model changed: {record['observed']['model']}")
    if not view["mismatch"]:
        problems.append("the requested/reported mismatch was not recorded")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(refusal)} level={claims['model']['level']} mismatch={view['mismatch']}",
        evidence={"refusal": refusal, "claims": claims, "mismatches": view["mismatches"], "problems": problems},
    )


@case(
    id="execution-provenance.fabricated-execution-id-refused",
    group="execution-provenance",
    title="A well-formed but engine-unknown execution id is not an execution",
    task="Attempt a rendered-evidence verification and a review binding with an invented exe id.",
    expectation="Both are refused because the engine did not create that execution for this run.",
    evaluation="Attempt both operations and read the refusals.",
    evidence_required="The two refusals and the unchanged evidence state.",
    layer="deterministic",
)
def provenance_fabricated_id(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    refusal = ""
    try:
        module.PROVENANCE.require_engine_execution(
            state, "exe_20260101T000000Z_deadbeef", label="a benchmark check",
        )
    except module.CONTRACTS.ContractError as exc:
        refusal = str(exc)
    problems = []
    if "did not create" not in refusal:
        problems.append(f"a fabricated id was accepted: {refusal!r}")
    review_problems = module.REVIEWS.independence_problems(
        state, "independent-reviewer",
        reviewer_execution="exe_20260101T000000Z_deadbeef",
        implementing_execution="exe_20260101T000000Z_00000001",
    )
    if not any("did not create" in item for item in review_problems):
        problems.append(f"a review bound fabricated executions: {review_problems}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(refusal)} review_refused={bool(review_problems)}",
        evidence={"refusal": refusal, "review_problems": review_problems, "problems": problems},
    )


@case(
    id="execution-provenance.stale-and-misattached-results-refused",
    group="execution-provenance",
    title="A result cannot be attached to the wrong revision, role or task",
    task="Attempt to verify one execution's result against a changed revision, another role and another task.",
    expectation="All three attempts are refused and the execution stays open.",
    evaluation="Call verify_result three ways and read the problems.",
    evidence_required="The three problem lists and the execution state.",
    layer="deterministic",
)
def provenance_stale_result(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    record = make_execution(module, state)
    stale = module.EXECUTION.verify_result(
        state, record["execution_id"], role="implementer", task_id="bench-S4B", revision_hash="cd" * 32,
    )
    wrong_role = module.EXECUTION.verify_result(state, record["execution_id"], role="reviewer", task_id="bench-S4B")
    wrong_task = module.EXECUTION.verify_result(state, record["execution_id"], role="implementer", task_id="other")
    problems = []
    if not any("different revision" in item for item in stale):
        problems.append(f"a stale revision was accepted: {stale}")
    if not any("not a reviewer" in item for item in wrong_role):
        problems.append(f"a wrong role was accepted: {wrong_role}")
    if not any("not other" in item for item in wrong_task):
        problems.append(f"a wrong task was accepted: {wrong_task}")
    if module.EXECUTION.execution(state, record["execution_id"])["state"] != "STARTED":
        problems.append("the refused attempts changed the execution state")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"stale={bool(stale)} role={bool(wrong_role)} task={bool(wrong_task)}",
        evidence={"stale": stale, "wrong_role": wrong_role, "wrong_task": wrong_task, "problems": problems},
    )


@case(
    id="execution-provenance.replay-and-duplicate-request-refused",
    group="execution-provenance",
    title="A replayed result and a duplicate provider request id are refused",
    task="Complete one execution twice and have two executions claim one provider request id.",
    expectation="The replay is refused; the duplicate request id is reported as a provenance conflict.",
    evaluation="Complete twice, record two provider observations with one request id and read the conflict.",
    evidence_required="The replay refusal and the conflict list.",
    layer="deterministic",
)
def provenance_replay(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    first = make_execution(module, state)
    second = make_execution(module, state, role="reviewer", adapter="fixture:review")
    module.EXECUTION.complete(state, first["execution_id"], result={"status": "ok"})
    refusal = ""
    try:
        module.EXECUTION.complete(state, first["execution_id"], result={"status": "ok"})
    except module.CONTRACTS.ContractError as exc:
        refusal = str(exc)
    module.PROVENANCE.record_provider_observation(
        state, first["execution_id"], provider="deepseek", model="deepseek-x",
        request_id="req_bench_1", source="adapter:reasoners",
    )
    module.PROVENANCE.record_provider_observation(
        state, second["execution_id"], provider="deepseek", model="deepseek-x",
        request_id="req_bench_1", source="adapter:reasoners",
    )
    conflicts = module.PROVENANCE.provider_request_problems(state)
    problems = []
    if not refusal:
        problems.append("a replayed result was accepted")
    if not any("req_bench_1" in item for item in conflicts):
        problems.append(f"the duplicate provider request id was not reported: {conflicts}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"replay_refused={bool(refusal)} conflicts={len(conflicts)}",
        evidence={"refusal": refusal, "conflicts": conflicts, "problems": problems},
    )


# =========================================================== capability registry


@case(
    id="capability-registry.declared-is-not-verified",
    group="capability-registry",
    title="A declared capability is never reported as verified",
    task="Declare a capability and attempt to observe it as VERIFIED without a verification record.",
    expectation="The declaration is DECLARED; the VERIFIED observation is refused.",
    evaluation="Declare, resolve the status, attempt the verification and read the refusal.",
    evidence_required="The resolved status, the refusal and the registry counters.",
    layer="deterministic",
)
def capability_declared_not_verified(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    module.CAPABILITIES.declare(state, capability_id="git", adapter="executable:git", family="tool")
    resolved = module.CAPABILITIES.capability_status(
        state, family="tool", adapter="executable:git", capability_id="git",
    )
    refusal = ""
    try:
        module.CAPABILITIES.observe(
            state, capability_id="git", adapter="executable:git", family="tool",
            status="VERIFIED", mechanism="claim",
            verification_id="vrf_20260101T000000Z_deadbeef", evidence=[{"detail": "x"}],
        )
    except module.CONTRACTS.ContractError as exc:
        refusal = str(exc)
    problems = []
    if resolved["status"] != "DECLARED":
        problems.append(f"declared status={resolved['status']}")
    if "existing verification record" not in refusal:
        problems.append(f"a declaration was promoted: {refusal!r}")
    if module.CAPABILITIES.summarise(state)["statuses"].get("verified", 0) != 0:
        problems.append("the registry counted a verification that never happened")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"status={resolved['status']} verify_refused={bool(refusal)}",
        evidence={"resolved": resolved, "refusal": refusal, "problems": problems},
    )


@case(
    id="capability-registry.exercised-requires-real-execution",
    group="capability-registry",
    title="An exercised capability needs the execution that exercised it",
    task="Attempt to record EXERCISED from a claim and then from a real engine execution.",
    expectation="The claim is refused; the engine execution establishes EXERCISED with evidence.",
    evaluation="Attempt both observations and read the refusal and the accepted record.",
    evidence_required="The refusal and the exercised record.",
    layer="deterministic",
)
def capability_exercised(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    refusal = ""
    try:
        module.CAPABILITIES.observe(
            state, capability_id="screenshot", adapter="fixture:capture", family="capture",
            status="EXERCISED", mechanism="claim",
        )
    except module.CONTRACTS.ContractError as exc:
        refusal = str(exc)
    execution = make_execution(module, state, role="validator", adapter="fixture:capture")
    record = module.CAPABILITIES.observe(
        state, capability_id="screenshot", adapter="fixture:capture", family="capture",
        status="EXERCISED", mechanism="engine-execution", execution=execution["execution_id"],
        evidence=[{"detail": "the capture execution produced a screenshot artifact"}],
    )
    problems = []
    if not refusal:
        problems.append("an exercised claim without an execution was accepted")
    if record["status"] != "EXERCISED" or record["execution"] != execution["execution_id"]:
        problems.append(f"exercised record={record['status']} execution={record['execution']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"claim_refused={bool(refusal)} exercised={record['status']}",
        evidence={"refusal": refusal, "record": record, "problems": problems},
    )


@case(
    id="capability-registry.unavailable-excluded-from-routing",
    group="capability-registry",
    title="An observed-unavailable capability is excluded from routing",
    task="Route design evidence through an adapter whose capability was observed unavailable.",
    expectation="The route is blocked with design-evidence-unavailable and the exclusion names the observation.",
    evaluation="Observe UNAVAILABLE, route the evidence need and read the decision.",
    evidence_required="The route decision, its candidates and the exclusion reason.",
    layer="deterministic",
)
def capability_unavailable_routing(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)

    class Stub:
        id = "stub-reference"

        def capabilities(self):
            return ("discover", "retrieve_content", "inspect_visual")

        def enabled(self):
            return True

    characterisation = {
        "characteristics": {"reference_research": {"value": "REQUIRED"}},
        "task_id": "bench-S4B", "characterisation_id": "ch_bench",
    }
    selected = module.ROUTING.route_evidence(
        state, stage="S4B", design_characterisation=characterisation,
        reference_adapters={"stub-reference": Stub()}, task_id="bench-S4B",
    )
    module.CAPABILITIES.observe(
        state, capability_id="retrieve_content", adapter="stub-reference", family="reference",
        status="UNAVAILABLE", mechanism="probe:endpoint", reason="the source is not reachable here",
        evidence=[{"detail": "the endpoint refused the connection"}],
    )
    blocked = module.ROUTING.route_evidence(
        state, stage="S4B", design_characterisation=characterisation,
        reference_adapters={"stub-reference": Stub()}, task_id="bench-S4B",
    )
    problems = []
    if selected["status"] != "selected":
        problems.append(f"the declared route was not selected: {selected['status']}")
    if blocked["status"] != "blocked" or blocked["rule"] != "design-evidence-unavailable":
        problems.append(f"the unavailable capability did not block: {blocked['status']}/{blocked['rule']}")
    if not any("unavailable" in item["reasons"][0] for item in blocked["exclusions"]):
        problems.append(f"the exclusion did not name the observation: {blocked['exclusions']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"declared={selected['status']} observed_unavailable={blocked['status']}",
        evidence={"selected": selected["status"], "blocked": blocked["exclusions"], "problems": problems},
    )


@case(
    id="capability-registry.evidence-policy-is-explicit",
    group="capability-registry",
    title="Strict routing does not accept a declaration, and the policy is recorded",
    task="Route the same evidence need under the declared and strict policies with no registry evidence.",
    expectation="Declared selects; strict blocks and records the policy it applied.",
    evaluation="Route twice and read the policy and the exclusion.",
    evidence_required="Both route decisions and the recorded policy.",
    layer="deterministic",
)
def capability_policy(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)

    class Stub:
        id = "stub-reference"

        def capabilities(self):
            return ("discover", "retrieve_content", "inspect_visual")

        def enabled(self):
            return True

    characterisation = {
        "characteristics": {"reference_research": {"value": "REQUIRED"}},
        "task_id": "bench-S4B", "characterisation_id": "ch_bench",
    }
    declared = module.ROUTING.route_evidence(
        state, stage="S4B", design_characterisation=characterisation,
        reference_adapters={"stub-reference": Stub()}, task_id="bench-S4B",
        evidence_policy="declared",
    )
    strict = module.ROUTING.route_evidence(
        state, stage="S4B", design_characterisation=characterisation,
        reference_adapters={"stub-reference": Stub()}, task_id="bench-S4B",
        evidence_policy="strict",
    )
    problems = []
    if declared["evidence_policy"] != "declared" or declared["status"] != "selected":
        problems.append(f"declared policy={declared['evidence_policy']} status={declared['status']}")
    if strict["status"] != "blocked" or strict["evidence_policy"] != "strict":
        problems.append(f"strict policy={strict['evidence_policy']} status={strict['status']}")
    if "policy 'strict'" not in json.dumps(strict["exclusions"]):
        problems.append(f"the exclusion did not name the policy: {strict['exclusions']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"declared={declared['status']} strict={strict['status']}",
        evidence={"declared": declared["candidates"][:1], "strict": strict["exclusions"], "problems": problems},
    )


@case(
    id="capability-registry.deterministic-probes-are-honest",
    group="capability-registry",
    title="Deterministic probes report availability and unavailability honestly",
    task="Probe a present executable, a missing executable and a fixture command.",
    expectation="Present reports AVAILABLE, missing reports UNAVAILABLE with a reason, the fixture command EXERCISES.",
    evaluation="Run the three probes and read their statuses and evidence.",
    evidence_required="The three probe records.",
    layer="deterministic",
)
def capability_probes(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    present = module.CAPABILITIES.run_probe(
        state, module.CAPABILITIES.ExecutableProbe("python", capability_id="python", family="tool"),
    )
    missing = module.CAPABILITIES.run_probe(
        state,
        module.CAPABILITIES.ExecutableProbe(
            "ariadne-definitely-missing-executable", capability_id="missing", family="tool",
        ),
    )
    fixture = module.CAPABILITIES.run_probe(
        state,
        module.CAPABILITIES.FixtureCommandProbe(
            [__import__("sys").executable, "-c", "print('fixture-ok')"],
            cwd=box.root / "probe-fixture", capability_id="fixture-command", family="tool",
        ),
    )
    problems = []
    if present["status"] != "AVAILABLE":
        problems.append(f"present executable={present['status']}")
    if missing["status"] != "UNAVAILABLE" or not missing["record"]["reason"]:
        problems.append(f"missing executable={missing['status']} reason={missing['record']['reason']!r}")
    if fixture["status"] != "EXERCISED":
        problems.append(f"fixture command={fixture['status']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"present={present['status']} missing={missing['status']} fixture={fixture['status']}",
        evidence={
            "present": present["record"], "missing": missing["record"], "fixture": fixture["record"],
            "problems": problems,
        },
    )


# =========================================================== review independence


@case(
    id="review-independence.execution-bound-not-label-bound",
    group="review-independence",
    title="Independence is bound to executions, not to labels",
    task="Compare a relabelled self-review, a fabricated pair and two engine-created executions.",
    expectation="The same execution is NONE, the fabricated pair is only DECLARED_DISTINCT and the engine pair is ENGINE_DISTINCT_EXECUTION.",
    evaluation="Compute the independence level for all three pairs.",
    evidence_required="The three levels and the refusal for the self-review.",
    layer="deterministic",
)
def review_independence_levels(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    implementer = make_execution(module, state)
    reviewer = make_execution(module, state, role="reviewer", adapter="fixture:worker")
    same = module.REVIEWS.independence_level(
        state, reviewer_execution=implementer["execution_id"],
        implementing_execution=implementer["execution_id"],
    )
    fabricated = module.REVIEWS.independence_level(
        state, reviewer_execution="exe_20260101T000000Z_00000000",
        implementing_execution="exe_20260101T000000Z_00000001",
    )
    engine = module.REVIEWS.independence_level(
        state, reviewer_execution=reviewer["execution_id"],
        implementing_execution=implementer["execution_id"],
    )
    relabelled = module.REVIEWS.independence_problems(
        state, "independent-reviewer",
        reviewer_execution=implementer["execution_id"],
        implementing_execution=implementer["execution_id"],
    )
    problems = []
    if same != "NONE":
        problems.append(f"same execution level={same}")
    if fabricated != "DECLARED_DISTINCT":
        problems.append(f"fabricated pair level={fabricated}")
    if engine != "ENGINE_DISTINCT_EXECUTION":
        problems.append(f"engine pair level={engine}")
    if not any("same execution" in item for item in relabelled):
        problems.append(f"the relabelled self-review was not refused: {relabelled}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"same={same} fabricated={fabricated} engine={engine}",
        evidence={"relabelled": relabelled, "problems": problems},
    )


@case(
    id="review-independence.distinct-runtime-and-provider",
    group="review-independence",
    title="Observed runtime and provider differences raise the independence level",
    task="Compare two executions with one runtime, then with different runtimes, then with different observed providers.",
    expectation="The level rises from ENGINE_DISTINCT_EXECUTION to DISTINCT_RUNTIME to DISTINCT_PROVIDER.",
    evaluation="Compute the level as each observed fact changes.",
    evidence_required="The three levels and the observed facts behind them.",
    layer="deterministic",
)
def review_independence_runtime(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    implementer = make_execution(module, state)
    reviewer = make_execution(module, state, role="reviewer", adapter="fixture:worker")
    same_runtime = module.REVIEWS.independence_level(
        state, reviewer_execution=reviewer["execution_id"],
        implementing_execution=implementer["execution_id"],
    )
    reviewer["adapter"] = "fixture:reviewer-runtime"
    distinct_runtime = module.REVIEWS.independence_level(
        state, reviewer_execution=reviewer["execution_id"],
        implementing_execution=implementer["execution_id"],
    )
    module.PROVENANCE.record_provider_observation(
        state, implementer["execution_id"], provider="deepseek", model="deepseek-x",
        source="adapter:reasoners",
    )
    module.PROVENANCE.record_provider_observation(
        state, reviewer["execution_id"], provider="anthropic", model="claude-x",
        source="adapter:reviewers",
    )
    distinct_provider = module.REVIEWS.independence_level(
        state, reviewer_execution=reviewer["execution_id"],
        implementing_execution=implementer["execution_id"],
    )
    problems = []
    if same_runtime != "ENGINE_DISTINCT_EXECUTION":
        problems.append(f"same runtime level={same_runtime}")
    if distinct_runtime != "DISTINCT_RUNTIME":
        problems.append(f"distinct runtime level={distinct_runtime}")
    if distinct_provider != "DISTINCT_PROVIDER":
        problems.append(f"distinct provider level={distinct_provider}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"same={same_runtime} runtime={distinct_runtime} provider={distinct_provider}",
        evidence={
            "reviewer_claims": module.PROVENANCE.identity_claims(reviewer),
            "implementer_claims": module.PROVENANCE.identity_claims(implementer),
            "problems": problems,
        },
    )


@case(
    id="review-independence.stale-reviewed-revision-refused",
    group="review-independence",
    title="A review cannot bind a revision the evidence no longer matches",
    task="Prepare a design critique whose rendered evidence belongs to a different revision.",
    expectation="The critique is refused because the evidence is stale for the reviewed revision.",
    evaluation="Record evidence for one revision, prepare the critique for another and read the refusal.",
    evidence_required="The refusal and the unchanged review list.",
    layer="deterministic",
)
def review_independence_stale(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    capture_dir = box.run_root
    capture_dir.mkdir(parents=True, exist_ok=True)
    adapter = module.RENDER.OfflineFixtureAdapter(
        capture_dir,
        {"scenes": [{
            "route": "/pricing", "viewport": {"width": 375, "height": 812},
            "dom": "<main><h1>Pricing</h1></main>",
        }]},
    )
    capture_execution = make_execution(module, state, role="validator", adapter="fixture:capture")
    evidence = module.RENDER.record(
        state, task_id="bench-S4B", revision_hash=REVISION,
        artifact=adapter.capture({"route": "/pricing", "kind": "screenshot"}),
        adapter="offline-fixture", capture_execution=capture_execution["execution_id"],
        requirement_id="signature-moment",
    )
    implementer = make_execution(module, state)
    reviewer = make_execution(module, state, role="reviewer", adapter="fixture:review")
    refusal = ""
    try:
        module.CRITIQUE.prepare_review(
            state, task_id="bench-S4B", direction_id="dsd_20260101T000000Z_deadbeef",
            requirement_ids=["signature-moment"], evidence_ids=[evidence["evidence_id"]],
            reviewer_role="independent-reviewer",
            reviewer_execution=reviewer["execution_id"],
            implementing_execution=implementer["execution_id"],
            revision_hash="cd" * 32,
        )
    except module.CONTRACTS.ContractError as exc:
        refusal = str(exc)
    problems = []
    if not refusal:
        problems.append("a stale revision was accepted for review")
    if state.get("design_reviews"):
        problems.append("a review record was written for the refused critique")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(refusal)}",
        evidence={"refusal": refusal, "reviews": state.get("design_reviews"), "problems": problems},
    )


# =========================================================== render verification


@case(
    id="render-verification.reproduction-must-be-a-new-artifact",
    group="render-verification",
    title="Re-hashing the captured artifact is not independent re-production",
    task="Attempt to verify a capture by re-opening the same file, then by re-producing a new one.",
    expectation="The re-open is refused; the new artifact verifies and records a verification record.",
    evaluation="Attempt both verifications and read the refusal and the verification record.",
    evidence_required="The refusal, the verification record and the dependency fingerprints.",
    layer="deterministic",
)
def render_reproduction(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    capture_dir = box.run_root
    capture_dir.mkdir(parents=True, exist_ok=True)
    adapter = module.RENDER.OfflineFixtureAdapter(
        capture_dir,
        {"scenes": [{
            "route": "/pricing", "viewport": {"width": 375, "height": 812},
            "dom": "<main><h1>Pricing</h1></main>",
        }]},
    )
    capture_execution = make_execution(module, state, role="validator", adapter="fixture:capture")
    verifier = make_execution(module, state, role="validator", adapter="fixture:render-verifier")
    evidence = module.RENDER.record(
        state, task_id="bench-S4B", revision_hash=REVISION,
        artifact=adapter.capture({"route": "/pricing", "kind": "screenshot"}),
        adapter="offline-fixture", capture_execution=capture_execution["execution_id"],
    )
    refusal = ""
    try:
        module.RENDER.verify(
            state, evidence["evidence_id"], verification_execution=verifier["execution_id"],
            reproduced_artifact={
                "path": str(evidence["artifact"]["path"]), "sha256": evidence["artifact"]["sha256"],
            },
            method="re-hash the original",
        )
    except module.CONTRACTS.ContractError as exc:
        refusal = str(exc)
    reproduced = capture_dir / "design-captures" / "reproduced" / "shot.png"
    reproduced.parent.mkdir(parents=True, exist_ok=True)
    reproduced.write_bytes(Path(evidence["artifact"]["path"]).read_bytes())
    module.RENDER.verify(
        state, evidence["evidence_id"], verification_execution=verifier["execution_id"],
        reproduced_artifact={"path": str(reproduced), "sha256": evidence["artifact"]["sha256"]},
        method="independent re-capture",
    )
    record = module.VERIFICATION.verification(state, evidence["verification_id"])
    problems = []
    if "re-production" not in refusal:
        problems.append(f"the re-open was not refused as re-production: {refusal!r}")
    if evidence["state"] != "VERIFIED" or record is None:
        problems.append(f"state={evidence['state']} verification={bool(record)}")
    if record and record["dependencies"]["source-revision"] != REVISION:
        problems.append(f"dependencies={record['dependencies']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"reopen_refused={bool(refusal)} state={evidence['state']} level={record and record['level']}",
        evidence={"refusal": refusal, "verification": record, "problems": problems},
    )


@case(
    id="render-verification.changed-capture-parameters-invalidate",
    group="render-verification",
    title="A changed capture parameter makes the rendered verification stale",
    task="Verify a capture and re-evaluate its currentness against changed capture parameters.",
    expectation="The verification is CURRENT for its parameters and STALE for the changed ones.",
    evaluation="Verify, evaluate currentness twice and read both verdicts.",
    evidence_required="The two currentness verdicts and the dependency fingerprints.",
    layer="deterministic",
)
def render_parameters(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    capture_dir = box.run_root
    capture_dir.mkdir(parents=True, exist_ok=True)
    adapter = module.RENDER.OfflineFixtureAdapter(
        capture_dir,
        {"scenes": [{
            "route": "/pricing", "viewport": {"width": 375, "height": 812},
            "dom": "<main><h1>Pricing</h1></main>",
        }]},
    )
    capture_execution = make_execution(module, state, role="validator", adapter="fixture:capture")
    verifier = make_execution(module, state, role="validator", adapter="fixture:render-verifier")
    evidence = module.RENDER.record(
        state, task_id="bench-S4B", revision_hash=REVISION,
        artifact=adapter.capture({"route": "/pricing", "kind": "screenshot"}),
        adapter="offline-fixture", capture_execution=capture_execution["execution_id"],
    )
    reproduced = capture_dir / "design-captures" / "reproduced" / "shot.png"
    reproduced.parent.mkdir(parents=True, exist_ok=True)
    reproduced.write_bytes(Path(evidence["artifact"]["path"]).read_bytes())
    module.RENDER.verify(
        state, evidence["evidence_id"], verification_execution=verifier["execution_id"],
        reproduced_artifact={"path": str(reproduced), "sha256": evidence["artifact"]["sha256"]},
        method="independent re-capture",
    )
    current = module.RENDER.verification_currentness(state, evidence["evidence_id"])
    changed = module.RENDER.verification_dependencies(evidence)
    changed["capture-parameters"] = "0" * 64
    stale = module.RENDER.verification_currentness(
        state, evidence["evidence_id"], current_dependencies=changed,
    )
    problems = []
    if current["state"] != "CURRENT":
        problems.append(f"current={current}")
    if stale["state"] != "STALE":
        problems.append(f"stale={stale}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"current={current['state']} changed={stale['state']}",
        evidence={"dependencies": module.RENDER.verification_dependencies(evidence), "problems": problems},
    )


@case(
    id="render-verification.declared-observer-never-self-verifies",
    group="render-verification",
    title="Declared evidence cannot be verified by re-production",
    task="Record a declared-observer artifact and attempt an independent verification of it.",
    expectation="The verification is refused, no verification record is written and the state stays RENDERED.",
    evaluation="Record, attempt the verification and read the refusal and the state.",
    evidence_required="The refusal, the record state and the verification list.",
    layer="deterministic",
)
def render_declared(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    shot = box.write("design/observer/home.png", "\x89PNG-declared\n")
    observer = module.RENDER.DeclaredObserverAdapter(
        method="operator recorded this with their own browser",
        environment={"browser": "operator's browser"},
    )
    artifact = observer.capture({
        "path": str(shot), "kind": "screenshot", "viewport": {"width": 375}, "observation": "",
    })
    record = module.RENDER.record(
        state, task_id="bench-S4B", revision_hash=REVISION, artifact=artifact,
        adapter="declared-observer",
    )
    verifier = make_execution(module, state, role="validator", adapter="fixture:render-verifier")
    refusal = ""
    try:
        module.RENDER.verify(
            state, record["evidence_id"], verification_execution=verifier["execution_id"],
            reproduced_artifact={"path": str(shot), "sha256": artifact.sha256},
            method="independent re-capture",
        )
    except module.CONTRACTS.ContractError as exc:
        refusal = str(exc)
    problems = []
    if "declared" not in refusal:
        problems.append(f"the declared ceiling was not named: {refusal!r}")
    if record["state"] != "RENDERED" or state.get("verifications"):
        problems.append(f"state={record['state']} verifications={len(state.get('verifications') or [])}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(refusal)} state={record['state']}",
        evidence={"refusal": refusal, "record": record, "problems": problems},
    )


# ========================================================= reference verification


@case(
    id="reference-verification.locator-is-not-retrieval",
    group="reference-verification",
    title="A locator string is not retrieval and an asserted digest is refused",
    task="Register a local reference, attempt to assert its digest and then retrieve it honestly.",
    expectation="The asserted digest is refused; the honest retrieval records local-read with remote origin unproven.",
    evaluation="Register, attempt the assertion, retrieve and read the mode and origin.",
    evidence_required="The refusal, the retrieval mode and the origin record.",
    layer="deterministic",
)
def reference_locator(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    source = box.write("design/references/local.md", "reference content\n")
    reference = module.REFERENCES.register(
        state, source="local", locator=str(source), title="local reference",
        source_type="local-file", adapter="local-reference", task_id="bench-S4B",
        revision_hash=REVISION,
    )
    refusal = ""
    try:
        module.REFERENCES.mark_accessible(
            state, reference["reference_id"], content_sha256="a" * 64,
        )
    except module.CONTRACTS.ContractError as exc:
        refusal = str(exc)
    module.REFERENCES.mark_accessible(
        state, reference["reference_id"], content_sha256=module.REFERENCES.digest_file(source),
    )
    problems = []
    if "does not match the local source" not in refusal:
        problems.append(f"an asserted digest was accepted: {refusal!r}")
    if reference["content"]["retrieval_mode"] != "local-read":
        problems.append(f"mode={reference['content']['retrieval_mode']}")
    if reference["content"]["origin"]["remote_origin_proven"] is not False:
        problems.append(f"origin={reference['content']['origin']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"asserted_refused={bool(refusal)} mode={reference['content']['retrieval_mode']}",
        evidence={"refusal": refusal, "content": reference["content"], "problems": problems},
    )


@case(
    id="reference-verification.origin-proven-only-by-reproduction",
    group="reference-verification",
    title="Remote origin is proven only by an independent retrieval verification",
    task="Retrieve a local reference, verify the retrieval with an engine execution and check the origin and currentness.",
    expectation="Before verification the origin is unproven; after it a verification record exists; changed content makes it stale.",
    evaluation="Retrieve, verify, read the origin and re-evaluate currentness against changed content.",
    evidence_required="The origin record, the verification record and the staleness verdict.",
    layer="deterministic",
)
def reference_origin(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    source = box.write("design/references/local.md", "reference content\n")
    reference = module.REFERENCES.register(
        state, source="local", locator=str(source), title="local reference",
        source_type="local-file", adapter="local-reference", task_id="bench-S4B",
        revision_hash=REVISION,
    )
    module.REFERENCES.mark_accessible(
        state, reference["reference_id"], content_sha256=module.REFERENCES.digest_file(source),
    )
    before = dict(reference["content"]["origin"])
    verifier = make_execution(module, state, role="validator", adapter="fixture:ref-verifier")
    re_retrieved = box.write("re-retrieved.md", source.read_text(encoding="utf-8"))
    module.REFERENCES.record_retrieval_verification(
        state, reference["reference_id"], verification_execution=verifier["execution_id"],
        reproduced_artifact={"path": str(re_retrieved)}, method="re-read the source",
    )
    record = module.VERIFICATION.verification(
        state, reference["retrieval_verification"]["verification_id"],
    )
    stale = module.REFERENCES.reference_currentness(
        state, reference["reference_id"], current_digest="0" * 64,
    )
    problems = []
    if before["remote_origin_proven"] is not False:
        problems.append(f"origin before verification={before}")
    if not record or record["level"] != "INDEPENDENTLY_REPRODUCED":
        problems.append(f"verification record={record}")
    if reference["content"]["origin"]["remote_origin_proven"] is not True:
        problems.append(f"origin after verification={reference['content']['origin']}")
    if stale["state"] != "STALE":
        problems.append(f"changed content currentness={stale}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"before={before['remote_origin_proven']} after={reference['content']['origin']['remote_origin_proven']} stale={stale['state']}",
        evidence={"verification": record, "stale": stale, "problems": problems},
    )


@case(
    id="reference-verification.claimed-origin-without-verification-refused",
    group="reference-verification",
    title="A claimed remote origin without a verification is a provenance problem",
    task="Present a reference record that claims a proven remote origin with no retrieval verification.",
    expectation="The provenance check reports it and the reference cannot be treated as verified.",
    evaluation="Run the cross-record provenance check and read the problem.",
    evidence_required="The provenance problems.",
    layer="deterministic",
)
def reference_claimed_origin(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    source = box.write("design/references/local.md", "reference content\n")
    reference = module.REFERENCES.register(
        state, source="local", locator=str(source), title="local reference",
        source_type="local-file", adapter="local-reference", task_id="bench-S4B",
        revision_hash=REVISION,
    )
    module.REFERENCES.mark_accessible(
        state, reference["reference_id"], content_sha256=module.REFERENCES.digest_file(source),
    )
    reference["content"]["origin"] = {"remote_origin_proven": True}
    problems_found = module.REFERENCES.provenance_problems(state)
    problems = []
    if not any("URL string is not retrieval proof" in item for item in problems_found):
        problems.append(f"the claimed origin was not reported: {problems_found}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"problems={len(problems_found)}",
        evidence={"provenance_problems": problems_found, "problems": problems},
    )


# =============================================================== decision plane


def choice_question(module, *, consequence="LOW", options=("TIMEOUT", "UNKNOWN")):
    return module.DECISIONS.contracts.DecisionQuestion(
        question_id="failure-class",
        instructions="Classify this failure into exactly one declared class.",
        primitive="ChoiceDecision", options=options, consequence=consequence,
    )


@case(
    id="decision-plane.valid-choice-decision-recorded",
    group="decision-plane",
    title="A valid bounded decision records its answer, provenance and policy version",
    task="Ask one choice question with a deterministic provider and read the decision record.",
    expectation="The batch and the decision record carry the provider, model version, contract and policy versions, and no authorization effect.",
    evaluation="Evaluate the batch and inspect the decision record.",
    evidence_required="The batch record and the decision record.",
    layer="deterministic",
)
def decision_valid(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = module.DECISIONS.providers.DeterministicProvider(
        script={"failure-class": {
            "answer": "TIMEOUT", "confidence": 0.8, "confidence_kind": "DERIVED_CONFIDENCE",
        }},
    )
    projection = module.DECISIONS.batch.project(entries={"command": {"timed_out": True}})
    batch = module.DECISIONS.batch.evaluate(
        state, questions=[choice_question(module)], projection=projection, provider=provider,
        task_id="bench-S4B",
    )
    record = module.DECISIONS.batch.decision(state, batch["results"][0]["decision_id"])
    problems = []
    if batch["status"] != "answered" or record["status"] != "answered":
        problems.append(f"batch={batch['status']} decision={record['status']}")
    if record["model_version"] != "1" or record["provider"] != "deterministic-fixture":
        problems.append(f"provider identity={record['provider']}/{record['model_version']}")
    if record["policy_version"] != module.DECISIONS.policy.POLICY_VERSION:
        problems.append(f"policy version={record['policy_version']}")
    if record["contract_version"] != module.CONTRACTS.DECISION_CONTRACT_VERSION:
        problems.append(f"contract version={record['contract_version']}")
    if record["authorization_effect"] != "none" or record["acted_on"]:
        problems.append(f"authorization effect={record['authorization_effect']} acted_on={record['acted_on']}")
    if record["state_digest"] != projection["digest"]:
        problems.append("the decision is not bound to the projected state digest")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"status={record['status']} answer={record['answer']!r} kind={record['confidence_kind']}",
        evidence={"batch": batch, "decision": record, "problems": problems},
    )


@case(
    id="decision-plane.invalid-answer-refused-not-coerced",
    group="decision-plane",
    title="An answer outside the declared space is refused, never coerced",
    task="Have the provider answer with a value outside the closed option set.",
    expectation="The decision is recorded invalid with the raw answer preserved and no acceptance.",
    evaluation="Evaluate the batch and read the decision status and problems.",
    evidence_required="The invalid decision record and the policy verdict absence.",
    layer="deterministic",
)
def decision_invalid(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = module.DECISIONS.providers.DeterministicProvider(
        script={"failure-class": {"answer": "AUTHORIZATION_FAILURE", "confidence": 0.99,
                                  "confidence_kind": "CALIBRATED_PROBABILITY"}},
    )
    projection = module.DECISIONS.batch.project(entries={"failure": {"source": "mystery"}})
    batch = module.DECISIONS.batch.evaluate(
        state, questions=[choice_question(module)], projection=projection, provider=provider,
    )
    record = module.DECISIONS.batch.decision(state, batch["results"][0]["decision_id"])
    problems = []
    if record["answer_valid"] is not False or record["status"] != "invalid":
        problems.append(f"status={record['status']} valid={record['answer_valid']}")
    if not any("outside the declared option set" in item for item in record["problems"]):
        problems.append(f"problems={record['problems']}")
    if record["policy_verdict"]:
        problems.append("an invalid answer received a policy verdict")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"status={record['status']} raw={record.get('raw')!r}",
        evidence={"decision": record, "problems": problems},
    )


@case(
    id="decision-plane.confidence-provenance-preserved",
    group="decision-plane",
    title="Self-reported confidence is preserved and never promoted",
    task="Ask a low-consequence and a medium-consequence question with self-reported confidence.",
    expectation="Low is accepted as decision evidence, medium is refused with a fallback, and the kind stays self-reported.",
    evaluation="Evaluate both and read the policy verdicts.",
    evidence_required="The two decision records and their verdicts.",
    layer="deterministic",
)
def decision_confidence(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = module.DECISIONS.providers.DeterministicProvider(
        script={"failure-class": {"answer": "TIMEOUT", "confidence": 0.4,
                                  "confidence_kind": "SELF_REPORTED_CONFIDENCE"}},
    )
    projection = module.DECISIONS.batch.project(entries={"failure": {"source": "mystery"}})
    low = module.DECISIONS.batch.evaluate(
        state, questions=[choice_question(module, consequence="LOW")], projection=projection, provider=provider,
    )
    medium = module.DECISIONS.batch.evaluate(
        state, questions=[choice_question(module, consequence="MEDIUM")], projection=projection, provider=provider,
    )
    low_record = module.DECISIONS.batch.decision(state, low["results"][0]["decision_id"])
    medium_record = module.DECISIONS.batch.decision(state, medium["results"][0]["decision_id"])
    problems = []
    if low_record["status"] != "answered" or low_record["confidence_kind"] != "SELF_REPORTED_CONFIDENCE":
        problems.append(f"low status={low_record['status']} kind={low_record['confidence_kind']}")
    if medium_record["status"] != "refused":
        problems.append(f"medium status={medium_record['status']}")
    if medium_record["confidence_kind"] != "SELF_REPORTED_CONFIDENCE":
        problems.append("the medium refusal rewrote the confidence kind")
    if medium_record["policy_verdict"].get("fallback") != "deterministic":
        problems.append(f"fallback={medium_record['policy_verdict'].get('fallback')}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"low={low_record['status']} medium={medium_record['status']} kind={medium_record['confidence_kind']}",
        evidence={"low": low_record, "medium": medium_record, "problems": problems},
    )


@case(
    id="decision-plane.missing-confidence-is-allowed-to-be-missing",
    group="decision-plane",
    title="A missing confidence is recorded as NONE, never guessed",
    task="Answer a low-consequence question with no confidence at all.",
    expectation="The confidence stays null with kind NONE, the verdict is accepted and marked low-confidence.",
    evaluation="Evaluate the batch and read the record and verdict.",
    evidence_required="The decision record with its null confidence.",
    layer="deterministic",
)
def decision_missing_confidence(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = module.DECISIONS.providers.DeterministicProvider(
        script={"failure-class": {"answer": "TIMEOUT"}},
    )
    projection = module.DECISIONS.batch.project(entries={"failure": {"source": "mystery"}})
    batch = module.DECISIONS.batch.evaluate(
        state, questions=[choice_question(module)], projection=projection, provider=provider,
    )
    record = module.DECISIONS.batch.decision(state, batch["results"][0]["decision_id"])
    problems = []
    if record["confidence"] is not None or record["confidence_kind"] != "NONE":
        problems.append(f"confidence={record['confidence']} kind={record['confidence_kind']}")
    if record["status"] != "answered" or not record["policy_verdict"].get("low_confidence"):
        problems.append(f"status={record['status']} verdict={record['policy_verdict']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"status={record['status']} confidence={record['confidence']} kind={record['confidence_kind']}",
        evidence={"decision": record, "problems": problems},
    )


@case(
    id="decision-plane.cannot-authorize-a-protected-action",
    group="decision-plane",
    title="A decision can never authorize a protected action",
    task="Ask a protected-consequence question with the strongest confidence and attempt to act on a refusal.",
    expectation="The protected question is refused regardless of confidence, and acting on a refused decision is refused.",
    evaluation="Evaluate the protected question and attempt to mark a refused decision as acted on.",
    evidence_required="The refusal, the verdict and the unchanged decision record.",
    layer="deterministic",
)
def decision_protected(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = module.DECISIONS.providers.DeterministicProvider(
        script={"failure-class": {"answer": "TIMEOUT", "confidence": 0.99,
                                  "confidence_kind": "CALIBRATED_PROBABILITY",
                                  "distribution": {"TIMEOUT": 0.99, "UNKNOWN": 0.01}}},
    )
    projection = module.DECISIONS.batch.project(entries={"failure": {"source": "mystery"}})
    batch = module.DECISIONS.batch.evaluate(
        state, questions=[choice_question(module, consequence="PROTECTED")],
        projection=projection, provider=provider,
    )
    record = module.DECISIONS.batch.decision(state, batch["results"][0]["decision_id"])
    refusal = ""
    try:
        module.DECISIONS.batch.mark_acted_on(
            state, record["decision_id"], action="grant G2",
        )
    except module.CONTRACTS.ContractError as exc:
        refusal = str(exc)
    protected_problems = module.DECISIONS.policy.protected_action_problems(record, "grant G2")
    problems = []
    if record["status"] != "refused":
        problems.append(f"the protected question was {record['status']}")
    if not refusal or not protected_problems:
        problems.append(f"acting on the refusal was not refused: {refusal!r}")
    if record["acted_on"] or record["resulting_action"]:
        problems.append("the refused decision recorded an action")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"status={record['status']} acted_on_refused={bool(refusal)}",
        evidence={"decision": record, "refusal": refusal, "protected": protected_problems, "problems": problems},
    )


@case(
    id="decision-plane.batch-questions-are-independent",
    group="decision-plane",
    title="Independent questions are answered in one provider call and never chained",
    task="Ask two independent questions in one batch and verify the call count and per-question records.",
    expectation="One provider call answers both; each decision carries its own question id and the shared state digest.",
    evaluation="Evaluate the batch, count the provider calls and read both records.",
    evidence_required="The batch record, the two decision records and the provider call log.",
    layer="deterministic",
)
def decision_batch(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    questions = [
        module.DECISIONS.contracts.DecisionQuestion(
            question_id="q-first", instructions="First?", primitive="BinaryDecision",
        ),
        module.DECISIONS.contracts.DecisionQuestion(
            question_id="q-second", instructions="Second?", primitive="BinaryDecision",
        ),
    ]
    provider = module.DECISIONS.providers.DeterministicProvider(script={
        "q-first": {"answer": "yes"},
        "q-second": {"answer": "no", "confidence": 0.7, "confidence_kind": "PROVIDER_PROBABILITY"},
    })
    projection = module.DECISIONS.batch.project(entries={"evidence": {"a": 1}})
    batch = module.DECISIONS.batch.evaluate(
        state, questions=questions, projection=projection, provider=provider,
    )
    records = [
        module.DECISIONS.batch.decision(state, item["decision_id"]) for item in batch["results"]
    ]
    problems = []
    if len(provider.calls) != 1:
        problems.append(f"provider calls={len(provider.calls)}")
    if {record["question_id"] for record in records} != {"q-first", "q-second"}:
        problems.append(f"questions={[record['question_id'] for record in records]}")
    if any(record["state_digest"] != projection["digest"] for record in records):
        problems.append("a decision is not bound to the shared state digest")
    if batch["status"] != "answered":
        problems.append(f"batch status={batch['status']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"calls={len(provider.calls)} status={batch['status']} questions={len(records)}",
        evidence={"batch": batch, "problems": problems},
    )


@case(
    id="decision-plane.deterministic-provider-failure-is-recorded",
    group="decision-plane",
    title="A provider failure is recorded as a failure and falls back deterministically",
    task="Have the provider fail and then classify an unmapped failure source with it.",
    expectation="The batch is failed with the reason, and classification falls back to UNKNOWN with escalation.",
    evaluation="Evaluate the batch, classify with the failing provider and read both outcomes.",
    evidence_required="The failed batch and the fallback classification.",
    layer="deterministic",
)
def decision_failure(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = module.DECISIONS.providers.DeterministicProvider(
        script={}, fail=("failure-class",),
    )
    projection = module.DECISIONS.batch.project(entries={"failure": {"source": "mystery"}})
    batch = module.DECISIONS.batch.evaluate(
        state, questions=[choice_question(module)], projection=projection, provider=provider,
    )
    result = module.EXECUTION.classify_with_decision(
        state, source="mystery-source", detail="the command never returned",
        provider=module.DECISIONS.providers.DeterministicProvider(script={}, fail=("failure-class",)),
        task_id="bench-S4B",
    )
    problems = []
    if batch["status"] != "failed" or not batch["provider_reason"]:
        problems.append(f"batch={batch['status']} reason={batch['provider_reason']!r}")
    if result["class"] != "UNKNOWN" or result["source"] != "fallback-unknown" or not result["escalation_required"]:
        problems.append(f"classification={result}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"batch={batch['status']} class={result['class']} escalation={result['escalation_required']}",
        evidence={"batch": batch, "classification": {k: v for k, v in result.items() if k != "decision"},
                  "problems": problems},
    )


@case(
    id="decision-plane.first-real-use-keeps-code-before-judgment",
    group="decision-plane",
    title="Failure classification uses code first and bounded judgement only when needed",
    task="Classify a mapped source, then an unmapped one, with and without an available provider.",
    expectation="Mapped sources never consult a provider; unmapped sources use the bounded decision; unavailable providers fall back to UNKNOWN.",
    evaluation="Classify four ways and count provider calls.",
    evidence_required="The four classifications and the call log.",
    layer="deterministic",
)
def decision_first_use(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    mapped = module.EXECUTION.classify_with_decision(state, source="routine")
    counting = module.DECISIONS.providers.DeterministicProvider(script={})
    mapped_with_provider = module.EXECUTION.classify_with_decision(
        state, source="routine", provider=counting,
    )
    scripted = module.DECISIONS.providers.DeterministicProvider(
        script={"failure-class": {"answer": "TIMEOUT", "confidence": 0.8,
                                  "confidence_kind": "DERIVED_CONFIDENCE"}},
    )
    decided = module.EXECUTION.classify_with_decision(
        state, source="mystery-source", detail="the command never returned", provider=scripted,
        task_id="bench-S4B",
        projection_entries={"command": {"returncode": None, "timed_out": True}},
    )
    unavailable = module.EXECUTION.classify_with_decision(
        state, source="mystery-source", provider=module.DECISIONS.providers.UnavailableProvider(),
    )
    problems = []
    if mapped["source"] != "deterministic" or mapped["class"] != "IMPLEMENTATION_FAILURE":
        problems.append(f"mapped={mapped['class']}/{mapped['source']}")
    if counting.calls:
        problems.append(f"the deterministic path consulted a provider {len(counting.calls)} time(s)")
    if mapped_with_provider["class"] != mapped["class"]:
        problems.append("a provider changed a deterministic classification")
    if decided["class"] != "TIMEOUT" or decided["source"] != "bounded-decision":
        problems.append(f"decided={decided['class']}/{decided['source']}")
    if unavailable["class"] != "UNKNOWN" or not unavailable["escalation_required"]:
        problems.append(f"unavailable={unavailable['class']} escalation={unavailable['escalation_required']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=(
            f"mapped={mapped['source']} provider_calls={len(counting.calls)} "
            f"decided={decided['source']} fallback={unavailable['source']}"
        ),
        evidence={
            "mapped": mapped, "decided": {k: v for k, v in decided.items() if k != "decision"},
            "unavailable": {k: v for k, v in unavailable.items() if k != "decision"},
            "problems": problems,
        },
    )


# ============================================================== false acceptance


@case(
    id="false-acceptance.fabricated-verification-evidence-refused",
    group="false-acceptance",
    title="A verification claiming evidence that does not exist is refused",
    task="Attempt to record an observation whose evidence artifact is a fabricated path.",
    expectation="The record is refused and no verification exists.",
    evaluation="Attempt the record and read the refusal and the verification list.",
    evidence_required="The refusal and the empty verification list.",
    layer="deterministic",
)
def false_acceptance_evidence(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    observer = make_execution(module, state, role="validator", adapter="fixture:observer")
    refusal = ""
    try:
        module.VERIFICATION.create(
            state, subject="claim", claim="the artifact exists", level="OBSERVED", method="hash",
            execution_id=observer["execution_id"], revision=REVISION,
            evidence=[{"path": str(box.root / "fabricated-log.txt")}],
        )
    except module.CONTRACTS.ContractError as exc:
        refusal = str(exc)
    problems = []
    if "does not exist" not in refusal:
        problems.append(f"a fabricated artifact was accepted: {refusal!r}")
    if state.get("verifications"):
        problems.append("a verification record was written")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(refusal)}",
        evidence={"refusal": refusal, "problems": problems},
    )


@case(
    id="false-acceptance.self-attested-verification-refused",
    group="false-acceptance",
    title="A verification with no execution and no evidence is refused",
    task="Attempt to record an OBSERVED verification from prose alone.",
    expectation="The refusal names the missing execution or anchor and the missing evidence.",
    evaluation="Attempt the record and read the refusal.",
    evidence_required="The refusal and the empty verification list.",
    layer="deterministic",
)
def false_acceptance_self_attested(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    refusal = ""
    try:
        module.VERIFICATION.create(
            state, subject="claim", claim="tests passed", level="OBSERVED", method="self-report",
            revision=REVISION, evidence=[],
        )
    except module.CONTRACTS.ContractError as exc:
        refusal = str(exc)
    problems = []
    if "needs the engine execution" not in refusal:
        problems.append(f"a self-attestation was accepted: {refusal!r}")
    if state.get("verifications"):
        problems.append("a verification record was written")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(refusal)}",
        evidence={"refusal": refusal, "problems": problems},
    )


@case(
    id="false-acceptance.stale-passing-evidence-does-not-close",
    group="false-acceptance",
    title="A passing verification from a changed revision does not answer as current",
    task="Record a verified claim, change its dependency and re-read the status.",
    expectation="The record answers as STALE and its established level is preserved as history.",
    evaluation="Verify, refresh against a changed dependency and read the effective level.",
    evidence_required="The refreshed record and the effective level.",
    layer="deterministic",
)
def false_acceptance_stale(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    observed = evidence_file(box, "observed.txt", "evidence\n")
    reproduced = evidence_file(box, "reproduced.txt", "evidence\n")
    digest = hashlib.sha256(observed.read_bytes()).hexdigest()
    observer = make_execution(module, state, role="validator", adapter="fixture:observer")
    verifier = make_execution(module, state, role="validator", adapter="fixture:verifier")
    record = module.VERIFICATION.create(
        state, subject="claim", claim="the artifact exists", level="VERIFIED", method="independent re-read",
        execution_id=observer["execution_id"], verifier_execution_id=verifier["execution_id"],
        revision=REVISION, evidence=[{"path": str(observed)}],
        reproduced_artifact={"path": str(reproduced), "sha256": digest},
        dependencies={"source-revision": REVISION},
    )
    refreshed = module.VERIFICATION.refresh(
        state, record["verification_id"], current={"source-revision": "cd" * 32},
    )
    problems = []
    if refreshed["freshness"] != "STALE" or module.VERIFICATION.effective_level(refreshed) != "STALE":
        problems.append(f"freshness={refreshed['freshness']} effective={module.VERIFICATION.effective_level(refreshed)}")
    if refreshed.get("established_level") != "VERIFIED":
        problems.append(f"established level={refreshed.get('established_level')}")
    if module.VERIFICATION.status(state, subject="claim")["level"] == "VERIFIED":
        problems.append("the status still answers as VERIFIED")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"freshness={refreshed['freshness']} established={refreshed.get('established_level')}",
        evidence={"verification": refreshed, "problems": problems},
    )


@case(
    id="false-acceptance.orphan-result-cannot-attach",
    group="false-acceptance",
    title="An orphan result cannot be attached to a new execution",
    task="Attempt to verify a result against another execution, task and revision.",
    expectation="Every mismatch is refused and the target execution is untouched.",
    evaluation="Attempt three attachments and read the problems.",
    evidence_required="The three problem lists.",
    layer="deterministic",
)
def false_acceptance_orphan(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    original = make_execution(module, state)
    module.EXECUTION.complete(state, original["execution_id"], result={"status": "ok"})
    fresh = make_execution(module, state, role="implementer", adapter="fixture:worker-2")
    problems_found = module.EXECUTION.verify_result(
        state, fresh["execution_id"], role="implementer", task_id="bench-S4B", revision_hash="cd" * 32,
    )
    wrong_task = module.EXECUTION.verify_result(state, fresh["execution_id"], role="implementer", task_id="other")
    problems = []
    if not any("different revision" in item for item in problems_found):
        problems.append(f"a stale revision was accepted: {problems_found}")
    if not any("not other" in item for item in wrong_task):
        problems.append(f"a wrong task was accepted: {wrong_task}")
    if module.EXECUTION.execution(state, fresh["execution_id"])["state"] != "STARTED":
        problems.append("the target execution changed")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"stale={bool(problems_found)} wrong_task={bool(wrong_task)}",
        evidence={"stale": problems_found, "wrong_task": wrong_task, "problems": problems},
    )


@case(
    id="false-acceptance.recovery-never-converts-ambiguity-into-success",
    group="false-acceptance",
    title="Recovery refuses to convert an ambiguous state into success",
    task="Ask recovery for proposals on a duplicate-result and an interrupted execution.",
    expectation="The ambiguous state is refused; the interrupted execution is abandoned as INTERRUPTED with no result claimed.",
    evaluation="Build the findings and read both proposals.",
    evidence_required="The two proposals and their reasons.",
    layer="deterministic",
)
def false_acceptance_recovery(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    record = make_execution(module, state)
    ambiguous = module.RECOVERY.proposal({"kind": "duplicate-result", "execution": record["execution_id"]}, state)
    interrupted = module.RECOVERY.proposal({"kind": "interrupted-execution", "execution": record["execution_id"]}, state)
    problems = []
    if ambiguous["safe"] or ambiguous["action"]:
        problems.append(f"the ambiguous state produced an action: {ambiguous}")
    if interrupted["action"] != "abandon-execution" or not interrupted["safe"]:
        problems.append(f"the interrupted execution proposal={interrupted}")
    if "result" in interrupted["reason"] and "does not claim any result" not in interrupted["reason"]:
        problems.append(f"the reason claims a result: {interrupted['reason']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"ambiguous_safe={ambiguous['safe']} interrupted={interrupted['action']}",
        evidence={"ambiguous": ambiguous, "interrupted": interrupted, "problems": problems},
    )


@case(
    id="false-acceptance.cli-and-engine-refuse-the-same-claim",
    group="false-acceptance",
    title="The CLI and the engine refuse the same fabricated claim identically",
    task="Attempt a fabricated execution provenance through the CLI and through the engine.",
    expectation="Both refuse with the same engine reason; neither surface accepts what the other refuses.",
    evaluation="Run the CLI command and the engine call and compare the refusals.",
    evidence_required="Both refusal strings.",
    layer="deterministic",
)
def false_acceptance_parity(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = ctx.sandbox()
    started = ctx.repo.cli(
        "start", "--run-root", str(box.run_root), "--project", str(box.project),
        "--run-id", "bench-ar203", "--request", "Parity check.",
    )
    if not started.ok:
        return Outcome("error", f"could not start a run: {started.tail(3)}")
    box.write("HANDOFF.md", FRONTEND_HANDOFF)
    box.write("PROJECT.md", "# PROJECT\n\nA small product site.\n")
    state = bench_state(box)
    engine_refusal = ""
    try:
        module.PROVENANCE.require_engine_execution(
            state, "exe_20260101T000000Z_deadbeef", label="a parity check",
        )
    except module.CONTRACTS.ContractError as exc:
        engine_refusal = str(exc)
    cli = ctx.repo.cli(
        "provenance", "--run-root", str(box.run_root), "--execution", "exe_20260101T000000Z_deadbeef",
    )
    combined = cli.combined
    problems = []
    if "did not create" not in engine_refusal:
        problems.append(f"the engine accepted the id: {engine_refusal!r}")
    if cli.returncode != 1 or "did not create" not in combined:
        problems.append(f"the CLI diverged: exit={cli.returncode} output={combined[-300:]!r}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"engine_refused={bool(engine_refusal)} cli_exit={cli.returncode}",
        evidence={"engine": engine_refusal, "cli": combined[-400:], "problems": problems},
    )
