"""AR-204 deterministic benchmark cases: harness economics and execution efficiency.

Every case is offline, deterministic and dependency-free. They test whether the
economics layer measures what it claims to measure, whether an optimisation keeps
the evidence it must keep, and whether cost pressure can be turned into a way
around capability, policy or verification. The groups follow the AR-204 brief:
economics accounting, request rendering, tool schemas, externalized output,
context economics, compaction, decision economics and orchestration economics.

The cases drive the engine modules through the runtime module
(``ctx.repo.module("ariadne.py")``), which is the same engine the CLI and the API
use; nothing here re-implements an engine rule.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .cases import Ctx, Outcome, case

REVISION = "ab" * 32
PROMPT_MARKER = "Do the task. This sentence must survive the compact profile."
SECRET = "sk-live-abcdefghijklmnopqrstuvwxyz0123456789"


def runtime(ctx: Ctx):
    return ctx.repo.module("ariadne.py")


def project_box(ctx: Ctx):
    box = ctx.sandbox()
    box.write("PROJECT.md", "# PROJECT\n\nA small product site.\n")
    box.write("AGENTS.md", "# AGENTS\n\n- Keep the site offline.\n")
    box.write("HANDOFF.md", "# HANDOFF\n\n## Worker execution contract\n\n| Field | Value |\n| --- | --- |\n| Role | bulk |\n")
    return box


def bench_state(box, **extra) -> dict:
    state = {
        "schema_version": 1,
        "run_id": "bench-ar204",
        "project": str(box.project),
        "run_root": str(box.run_root),
        "packets": [{"id": "bench-S4B", "stage": "S4B", "path": str(box.run_root / "bench-S4B")}],
        "approvals": [],
    }
    state.update(extra)
    return state


def make_execution(module, state, *, role="implementer", adapter="fixture:worker", task_id="bench-S4B",
                   requested=None, start=True, complete=True, usage=None, parent=""):
    record = module.EXECUTION.create(
        state, task_id=task_id, role=role, adapter=adapter, parent=parent,
        requested=requested or {"provider": "deepseek", "model": "deepseek-x", "worker_role": "bulk"},
        revision={"revision_hash": REVISION},
    )
    if start:
        module.EXECUTION.mark_started(state, record["execution_id"])
    if usage is not None:
        module.EXECUTION.record_usage(state, record["execution_id"], source="fixture-adapter", **usage)
    if complete:
        module.EXECUTION.complete(state, record["execution_id"], result={"ok": True}, evidence=("fixture",))
    return record


def verify_task(module, box, state, *, subject="bench-S4B", execution=None, usage=None):
    """Build a real VERIFIED chain so the task counts as a verified completion."""
    observed = box.write("evidence/observed.txt", "artifact\n")
    reproduced = box.write("evidence/reproduced.txt", "artifact\n")
    digest = hashlib.sha256(observed.read_bytes()).hexdigest()
    observer = make_execution(
        module, state, role="implementer", adapter="fixture:observer",
        requested={"provider": "deepseek", "model": "deepseek-x", "worker_role": "bulk"},
        usage=usage or {"input_tokens": 100, "output_tokens": 50, "request_count": 1},
    )
    verifier = make_execution(
        module, state, role="validator", adapter="fixture:verifier",
        requested={"provider": "deepseek", "model": "deepseek-x"},
        usage={"input_tokens": 30, "output_tokens": 10, "request_count": 1},
    )
    record = module.VERIFICATION.create(
        state, subject=subject, claim="the task artifact exists", level="VERIFIED",
        method="independent re-read", execution_id=observer["execution_id"],
        verifier_execution_id=verifier["execution_id"], revision=REVISION,
        evidence=[{"path": str(observed)}],
        reproduced_artifact={"path": str(reproduced), "sha256": digest},
        dependencies={"source-revision": REVISION}, task_id=subject,
    )
    return record, observer, verifier


def packet_text(module, box, *, prompt=PROMPT_MARKER, stage="S4B", extra="") -> str:
    transport = runtime_packet_section(stage)
    prompt_section = (
        f"===== BEGIN current {stage} prompt block | SOURCE prompts/build-kickoff.md | "
        f"SOURCE-SHA256 {'a' * 64} | CONTENT-SHA256 {'b' * 64} =====\n{prompt}\n"
        f"===== END current {stage} prompt block =====\n"
    )
    project_section = (
        f"===== BEGIN PROJECT.md | SOURCE {box.project / 'PROJECT.md'} | SOURCE-SHA256 {'c' * 64} | "
        f"CONTENT-SHA256 {'d' * 64} =====\n# PROJECT\n\nA small product site.\n"
        f"===== END PROJECT.md =====\n"
    )
    return transport + extra + prompt_section + project_section


def runtime_packet_section(stage="S4B") -> str:
    return (
        f"ARIADNE {stage} STAGE PACKET\nPacket ID: bench-{stage}\nProvider: implementation-worker\n"
        "Status: PREPARED ONLY — THE STAGE HAS NOT RUN\n\n"
        "TRANSPORT NOTICE\nThis packet is a generated transport artifact. The named source files remain canonical.\n"
        "Do not copy Ariadne policies or templates permanently into the project repository.\n\n"
        "Ariadne source commit: 0123456789abcdef0123456789abcdef01234567\n"
        "Parent packet: none — initial stage\n"
        "READ me: api_key = " + SECRET + "\n\n"
    )


# =========================================================== economics accounting


@case(
    id="economics-accounting.task-tree-totals-correct",
    group="economics-accounting",
    title="A task tree totals every node that spent something",
    task="Create a worker, a repair, a validation and a decision batch on one task and read the task cost.",
    expectation="Every node appears in the tree and the totals are the exact sum of the measured fields.",
    evaluation="Create the executions, record usage, build the tree and compare the totals with the inputs.",
    evidence_required="The tree, the cost totals and the per-node usage.",
    layer="deterministic",
)
def economics_task_tree(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    worker = make_execution(module, state, complete=False,
                            usage={"input_tokens": 1000, "output_tokens": 200, "request_count": 2})
    module.EXECUTION.fail(state, worker["execution_id"], source="routine", evidence=("fixture",), detail="first attempt")
    repair = make_execution(module, state, usage={"input_tokens": 400, "output_tokens": 90, "request_count": 1},
                            parent=worker["execution_id"])
    validator = make_execution(module, state, role="validator", adapter="fixture:validator",
                               usage={"input_tokens": 50, "output_tokens": 20, "request_count": 1})
    tree = module.ECONOMICS.task_tree(state, "bench-S4B")
    cost = module.ECONOMICS.task_cost(state, "bench-S4B")
    problems = []
    if tree["executions"] != 3:
        problems.append(f"the tree counted {tree['executions']} executions, not 3")
    if tree["failed_executions"] != 1:
        problems.append(f"the tree counted {tree['failed_executions']} failures, not 1")
    expected = {"input_tokens": 1450, "output_tokens": 310, "request_count": 4}
    if cost["totals"] != expected:
        problems.append(f"totals {cost['totals']} != {expected}")
    if cost["usage_complete"] is not True:
        problems.append("a fully measured task reported usage_complete=false")
    if cost["monetary"]["monetary"] != "UNKNOWN":
        problems.append(f"monetary cost was produced without a provider figure: {cost['monetary']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"nodes={tree['executions']} failed={tree['failed_executions']} totals={cost['totals']}",
        evidence={"tree": tree, "totals": cost["totals"], "monetary": cost["monetary"], "problems": problems},
    )


@case(
    id="economics-accounting.cached-and-uncached-preserved",
    group="economics-accounting",
    title="Cached and uncached input tokens stay separate",
    task="Record cached and uncached input tokens and read the task totals.",
    expectation="Both fields survive into the task totals and neither is collapsed into the other.",
    evaluation="Record the usage and read the totals.",
    evidence_required="The recorded usage values and the task totals.",
    layer="deterministic",
)
def economics_cached_split(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    make_execution(module, state, usage={
        "input_tokens": 1000, "cached_input_tokens": 800, "uncached_input_tokens": 200,
        "output_tokens": 40, "request_count": 1,
    })
    cost = module.ECONOMICS.task_cost(state, "bench-S4B")
    view = module.ECONOMICS.cache_observation(state, module.EXECUTION.executions(state)[0]["execution_id"])
    problems = []
    if cost["totals"].get("cached_input_tokens") != 800 or cost["totals"].get("uncached_input_tokens") != 200:
        problems.append(f"the cache split did not survive: {cost['totals']}")
    if cost["totals"].get("input_tokens") != 1000:
        problems.append("the provider input total was not preserved")
    if view:
        problems.append("a cache observation appeared without one being recorded")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"cached={cost['totals'].get('cached_input_tokens')} uncached={cost['totals'].get('uncached_input_tokens')}",
        evidence={"totals": cost["totals"], "problems": problems},
    )


@case(
    id="economics-accounting.unknown-usage-stays-unknown",
    group="economics-accounting",
    title="An unmeasured task reports unknown rather than zero",
    task="Create a task with no measured usage and read its cost.",
    expectation="The monetary figure is UNKNOWN, usage_complete is false and no token total is invented.",
    evaluation="Create the execution without usage and read the cost view.",
    evidence_required="The cost view and the list of executions without usage.",
    layer="deterministic",
)
def economics_unknown_stays_unknown(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    execution = make_execution(module, state, usage=None)
    cost = module.ECONOMICS.task_cost(state, "bench-S4B")
    problems = []
    if cost["monetary"].get("monetary") != "UNKNOWN":
        problems.append(f"monetary cost was invented: {cost['monetary']}")
    if cost["usage_complete"] is not False:
        problems.append("an unmeasured task claimed complete usage")
    if cost["totals"]:
        problems.append(f"token totals were invented from nothing: {cost['totals']}")
    if execution["execution_id"] not in cost["nodes_without_usage"]:
        problems.append("the unmeasured execution was not listed")
    if cost["totals"].get("input_tokens") == 0:
        problems.append("an unmeasured field was rendered as zero")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"monetary={cost['monetary'].get('monetary')} complete={cost['usage_complete']} totals={cost['totals']}",
        evidence={"cost": cost, "problems": problems},
    )


@case(
    id="economics-accounting.failed-attempt-included-in-task-cost",
    group="economics-accounting",
    title="A failed attempt is part of what the task cost",
    task="Fail an execution with measured usage, repair it and compare the cost with and without the failure.",
    expectation="The failed attempt's usage is included in the task total.",
    evaluation="Record usage on a failed execution and read the task totals.",
    evidence_required="The failure record, the usage and the totals.",
    layer="deterministic",
)
def economics_failed_attempt(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    failed = make_execution(module, state, complete=False,
                            usage={"input_tokens": 900, "output_tokens": 300, "request_count": 2})
    module.EXECUTION.fail(state, failed["execution_id"], source="routine", evidence=("fixture",), detail="broken")
    make_execution(module, state, usage={"input_tokens": 100, "output_tokens": 10, "request_count": 1})
    cost = module.ECONOMICS.task_cost(state, "bench-S4B")
    problems = []
    if cost["totals"].get("input_tokens") != 1000:
        problems.append(f"the failed attempt was excluded: {cost['totals']}")
    if cost["failed_executions"] != 1:
        problems.append("the failed execution was not counted")
    if cost["failed_executions"] and cost["totals"].get("output_tokens") != 310:
        problems.append(f"failed output tokens were dropped: {cost['totals']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"failed={cost['failed_executions']} totals={cost['totals']}",
        evidence={"cost": cost, "problems": problems},
    )


@case(
    id="economics-accounting.review-cost-in-verified-completion",
    group="economics-accounting",
    title="Review and validation spend count toward the verified completion cost",
    task="Build a verified completion with an observer, a verifier and a reviewer and read the metric.",
    expectation="The metric is labelled verified_completion_cost and includes every measured execution's usage.",
    evaluation="Create the chain, record usage on each node and read the verified completion cost.",
    evidence_required="The verification record, the tree and the metric.",
    layer="deterministic",
)
def economics_verified_cost(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    record, observer, verifier = verify_task(module, box, state)
    reviewer = make_execution(module, state, role="reviewer", adapter="fixture:reviewer",
                              requested={"provider": "deepseek", "model": "deepseek-x"},
                              usage={"input_tokens": 70, "output_tokens": 30, "request_count": 1})
    metric = module.ECONOMICS.verified_completion_cost(state, "bench-S4B")
    problems = []
    if not metric["verified"] or metric["cost_label"] != "verified_completion_cost":
        problems.append(f"the task was not reported as verified: {metric['verification']}")
    if metric["totals"].get("input_tokens") != 200:
        problems.append(f"the review/validation spend is missing: {metric['totals']}")
    if metric["executions"] != 3:
        problems.append(f"the metric counted {metric['executions']} executions, not 3")
    if not record.get("verification_id") or not reviewer.get("execution_id") or not verifier.get("execution_id"):
        problems.append("the chain did not create real records")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"verified={metric['verified']} executions={metric['executions']} totals={metric['totals']}",
        evidence={"metric": metric, "problems": problems},
    )


# =========================================================== request rendering


@case(
    id="request-rendering.stable-render-byte-identical",
    group="request-rendering",
    title="The same stable prefix renders byte-identical twice",
    task="Render identical requests twice and compare the stable prefix bytes.",
    expectation="The stable prefix digest and bytes are identical; a changed stable segment changes them.",
    evaluation="Render twice, compare, change a stable segment and compare again.",
    evidence_required="Both prefix digests and the byte counts.",
    layer="deterministic",
)
def rendering_byte_identical(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    rendering = module.HARNESS
    messages = [
        rendering.message(role="system", section="engine", text="engine context", bucket="SYSTEM"),
        rendering.message(role="system", section="policy", text="policy text", bucket="POLICY"),
        rendering.message(role="user", section="task", text="packet-1", bucket="TASK", stability="volatile"),
    ]
    first = rendering.render_request(provider="p", model="m", messages=messages)
    second = rendering.render_request(provider="p", model="m", messages=messages)
    changed_messages = [dict(item) for item in messages]
    changed_messages[1] = rendering.message(role="system", section="policy", text="different policy", bucket="POLICY")
    third = rendering.render_request(provider="p", model="m", messages=changed_messages)
    same = module.SERIALIZATION.prefix_identity(first["stable_prefix"], second["stable_prefix"])
    changed = module.SERIALIZATION.prefix_identity(first["stable_prefix"], third["stable_prefix"])
    problems = []
    if not same["identical"]:
        problems.append(f"two identical renders differed: {same}")
    if changed["identical"]:
        problems.append("changing a stable segment did not change the prefix digest")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"identical={same['identical']} prefix={first['stable_prefix']['stable_prefix_bytes']} bytes changed={not changed['identical']}",
        evidence={"same": same, "changed": changed, "problems": problems},
    )


@case(
    id="request-rendering.volatile-data-does-not-mutate-stable-prefix",
    group="request-rendering",
    title="Volatile task data does not move the stable prefix",
    task="Render two requests that differ only in the volatile task id and compare the stable prefixes.",
    expectation="The stable prefix is unchanged while the packet id the volatile segment carries differs.",
    evaluation="Render with two different volatile segments and compare.",
    evidence_required="Both prefix digests and the volatile sections.",
    layer="deterministic",
)
def rendering_volatile_isolated(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    rendering = module.HARNESS
    def build(task_id: str) -> dict:
        return rendering.render_request(provider="p", model="m", messages=[
            rendering.message(role="system", section="engine", text="engine context", bucket="SYSTEM"),
            rendering.message(role="user", section="task", text=f"Packet ID: {task_id}", bucket="TASK",
                              stability="volatile"),
        ])
    first = build("packet-one")
    second = build("packet-two")
    same = module.SERIALIZATION.prefix_identity(first["stable_prefix"], second["stable_prefix"])
    problems = []
    if not same["identical"]:
        problems.append("a volatile value changed the stable prefix")
    if first["stable_prefix"]["volatile_bytes"] == second["stable_prefix"]["volatile_bytes"] and first[
        "stable_prefix"]["volatile_bytes"] == 0:
        problems.append("the volatile segment was not measured")
    if first["volatile_sections"] == []:
        problems.append("the volatile section was not reported")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"stable_identical={same['identical']} volatile={first['stable_prefix']['volatile_bytes']} bytes",
        evidence={"same": same, "first": first["stable_prefix"], "problems": problems},
    )


@case(
    id="request-rendering.source-buckets-sum-correctly",
    group="request-rendering",
    title="Source buckets are attributable and sum to the measured size",
    task="Render a packet with policy, project and task sources and read the bucket accounting.",
    expectation="Each source lands in its own bucket and the byte totals equal the measured sizes.",
    evaluation="Render the packet and compare the bucket byte totals with the section sizes.",
    evidence_required="The harness map rows and the bucket totals.",
    layer="deterministic",
)
def rendering_buckets_sum(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    text = packet_text(module, box)
    mapping = module.HARNESS.packet_map(text)
    buckets = mapping["source_buckets"]["buckets"]
    total = sum(int(entry["bytes"]) for entry in buckets.values())
    problems = []
    if "SYSTEM" not in buckets:
        problems.append(f"the transport scaffolding was not attributed to SYSTEM: {sorted(buckets)}")
    if "PROJECT_FACTS" not in buckets:
        problems.append(f"PROJECT.md was not attributed to PROJECT_FACTS: {sorted(buckets)}")
    if total != mapping["measured_size"]["total_bytes"]:
        problems.append(f"bucket bytes {total} != measured size {mapping['measured_size']['total_bytes']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"buckets={sorted(buckets)} total={total} bytes",
        evidence={"buckets": buckets, "measured_size": mapping["measured_size"], "problems": problems},
    )


@case(
    id="request-rendering.secret-redaction",
    group="request-rendering",
    title="A rendered request never carries a detected secret",
    task="Render a packet that contains a provider key and read the render.",
    expectation="The key is replaced by a stable marker, the count is reported and the marker is not the secret.",
    evaluation="Render, search for the secret and compare two renders of the same secret.",
    evidence_required="The render text, the redaction count and the marker.",
    layer="deterministic",
)
def rendering_redaction(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    text = packet_text(module, box)
    mapping = module.HARNESS.packet_map(text)
    rendered = "\n".join(str(item["text"]) for item in mapping["sections"])
    problems = []
    if SECRET in rendered:
        problems.append("the rendered map still contains the secret")
    if mapping["measured_size"]["redactions"] < 1:
        problems.append("the redaction was not counted")
    again = module.HARNESS.redact(f"key={SECRET}")
    if again["text"] != module.HARNESS.redact(f"key={SECRET}")["text"]:
        problems.append("two redactions of the same secret were not stable")
    if SECRET in again["text"]:
        problems.append("the redacted text still contains the secret")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"redactions={mapping['measured_size']['redactions']} secret_present={SECRET in rendered}",
        evidence={"marker": again["text"], "kinds": again["kinds"], "problems": problems},
    )


@case(
    id="request-rendering.compact-profile-preserves-sources",
    group="request-rendering",
    title="The compact prompt profile touches only the transport scaffolding",
    task="Apply the compact_v2 profile to a packet and compare the source sections with the legacy render.",
    expectation="Scaffolding bytes are removed, the prompt block and every source are byte-identical.",
    evaluation="Render both profiles, compare the section digests and diff the scaffolding.",
    evidence_required="Both renders and the removed byte count.",
    layer="deterministic",
)
def rendering_compact_profile(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    text = packet_text(module, box)
    legacy = module.PROMPTING.compact_packet_text(text, profile="legacy")
    compact = module.PROMPTING.compact_packet_text(text, profile="compact_v2")
    legacy_map = module.HARNESS.packet_map(legacy["text"])
    compact_map = module.HARNESS.packet_map(compact["text"])
    legacy_sections = [(item["label"], item["digest"]) for item in legacy_map["sections"][1:]]
    compact_sections = [(item["label"], item["digest"]) for item in compact_map["sections"][1:]]
    problems = []
    if legacy["text"] != text:
        problems.append("the legacy profile changed the packet")
    if legacy_sections != compact_sections:
        problems.append("the compact profile changed a source section")
    if compact["removed_bytes"] <= 0:
        problems.append("the compact profile removed nothing from the scaffolding")
    if PROMPT_MARKER not in compact["text"]:
        problems.append("the compact profile lost the stage prompt block")
    if compact["sources_touched"]:
        problems.append("the compact profile reported touching the sources")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"removed={compact['removed_bytes']} bytes sections_identical={legacy_sections == compact_sections}",
        evidence={"applied": compact["applied"], "removed": compact["removed_bytes"], "problems": problems},
    )


# ================================================================ tool schemas


@case(
    id="tool-schemas.core-schemas-loaded",
    group="tool-schemas",
    title="Core capabilities are always selected and their declaration size is measured",
    task="Select packs for a backend stage and read the core declaration.",
    expectation="The core pack is selected with its measured size and the five first-turn capabilities.",
    evaluation="Select packs, read the core members and compare the size with the files on disk.",
    evidence_required="The selection, the core members and the measured size.",
    layer="deterministic",
)
def tools_core_loaded(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    root = ctx.repo.root
    selection = module.TOOLING.select_packs(stage="S4B")
    sizes = module.TOOLING.pack_sizes(root=root)
    problems = []
    if "core" not in selection["packs"]:
        problems.append("the core pack was not selected")
    if selection["packs"] != ["core"]:
        problems.append(f"a backend stage selected extra packs: {selection['packs']}")
    if set(module.TOOLING.CORE_CAPABILITIES) != {"read", "search", "edit", "shell", "return-handoff"}:
        problems.append(f"the core capability set changed: {module.TOOLING.CORE_CAPABILITIES}")
    if sizes["core_bytes"] <= 0:
        problems.append("the core declaration size was not measured")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"core={sizes['core_bytes']} bytes members={len(module.TOOLING.CORE_CAPABILITIES)}",
        evidence={"selection": selection, "sizes": sizes, "problems": problems},
    )


@case(
    id="tool-schemas.unused-pack-omitted",
    group="tool-schemas",
    title="An unused capability pack is omitted with a recorded reason",
    task="Select packs for a backend repair task and read the deferred packs.",
    expectation="Design, research, verification and writing are deferred; the deferrable byte total is measured.",
    evaluation="Select packs and compare the deferred list with the pack registry.",
    evidence_required="The selection and the deferred byte total.",
    layer="deterministic",
)
def tools_unused_omitted(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    selection = module.TOOLING.select_packs(stage="S4B")
    sizes = module.TOOLING.pack_sizes(root=ctx.repo.root)
    problems = []
    for pack in ("design", "research", "verification", "writing", "social", "capture"):
        if pack not in selection["deferred"]:
            problems.append(f"{pack} was not deferred for a backend stage")
    if sizes["deferrable_bytes"] <= 0:
        problems.append("the deferrable byte total was not measured")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"deferred={selection['deferred']} deferrable={sizes['deferrable_bytes']} bytes",
        evidence={"selection": selection, "sizes": sizes, "problems": problems},
    )


@case(
    id="tool-schemas.requested-pack-loaded",
    group="tool-schemas",
    title="A pack a task requires is selected with its reason",
    task="Select packs for a design task that selected the reference-analysis skill.",
    expectation="Design, research and their reasons are recorded; the required capability is provided.",
    evaluation="Select packs with a stage, skills and required capabilities and read the reasons.",
    evidence_required="The selection reasons and the loaded member list.",
    layer="deterministic",
)
def tools_requested_loaded(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    selection = module.TOOLING.select_packs(
        stage="S3", selected_skills=["reference-analysis"], required_capabilities=["design-direction"],
    )
    loaded = {item["id"] for item in module.TOOLING.loaded_declarations(selection["packs"], root=ctx.repo.root)}
    problems = []
    if "design" not in selection["packs"] or "research" not in selection["packs"]:
        problems.append(f"the requested packs were not selected: {selection['packs']}")
    if "design-direction-skill" not in loaded or "reference-analysis-skill" not in loaded:
        problems.append(f"the loaded declarations do not include the required members: {sorted(loaded)}")
    if not selection["reasons"].get("design") or not selection["reasons"].get("research"):
        problems.append("a selected pack carried no reason")
    if module.TOOLING.required_capability_problems(["design-direction-skill"], sorted(loaded)):
        problems.append("a required capability was reported missing after selection")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"packs={selection['packs']} reasons={len(selection['reasons'])}",
        evidence={"selection": selection, "loaded": sorted(loaded), "problems": problems},
    )


@case(
    id="tool-schemas.missing-required-capability-refuses",
    group="tool-schemas",
    title="A required capability that is not loaded refuses rather than continuing",
    task="Ask for a pack list that omits a required capability and read the guard.",
    expectation="The guard reports the missing capability and does not silently proceed.",
    evaluation="Call the guard with a capability the selection does not provide.",
    evidence_required="The guard's problems and the selection it was checked against.",
    layer="deterministic",
)
def tools_missing_refuses(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    selection = module.TOOLING.select_packs(stage="S4B")
    guard = module.TOOLING.required_capability_problems(["rendered-evidence"], selection["packs"])
    offload = module.TOOLING.offload_safety([
        {"pack": "capture", "required_frequency": 0.9, "call_error_rate": None, "policy_required": True},
        {"pack": "writing", "required_frequency": 0.1, "call_error_rate": 0.0, "policy_required": False},
    ])
    problems = []
    if not guard:
        problems.append("the guard accepted a missing required capability")
    decisions = {item["pack"]: item for item in offload["decisions"]}
    if decisions["capture"]["safe_to_offload"]:
        problems.append("offloading was reported safe for a frequently required, policy-required pack")
    if not decisions["writing"]["safe_to_offload"]:
        problems.append("offloading was reported unsafe for a rarely required pack with no findings")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"refused={bool(guard)} capture_offload_safe={decisions['capture']['safe_to_offload']}",
        evidence={"guard": guard, "offload": offload, "problems": problems},
    )


# ========================================================== externalized output


def externalized_case_setup(ctx: Ctx):
    module = runtime(ctx)
    box = project_box(ctx)
    text = "\n".join(f"line {index}: compiled module {index}" for index in range(2000))
    record = module.ARTIFACTS.externalize(
        box.run_root, data=text, tool="shell", command="npm run build", task_id="bench-S4B",
    )
    return module, box, record, text


@case(
    id="externalized-output.large-output-stored-completely",
    group="externalized-output",
    title="A large output is stored completely, not truncated",
    task="Externalize a 78 KB output and read the artifact from disk.",
    expectation="The artifact contains every byte and the status is excerpt plus artifact.",
    evaluation="Externalize, read the file and compare its length with the input.",
    evidence_required="The artifact record, the stored file and its size.",
    layer="deterministic",
)
def external_stored_completely(ctx: Ctx) -> Outcome:
    module, box, record, text = externalized_case_setup(ctx)
    stored = Path(record["path"]).read_bytes()
    problems = []
    if not record["stored"] or record["status"] == module.ARTIFACTS.STATUS_INLINE:
        problems.append(f"the large output was not externalized: {record['status']}")
    if stored.decode("utf-8") != text:
        problems.append("the stored artifact does not contain the complete output")
    if record["size"] != len(text.encode("utf-8")):
        problems.append(f"the recorded size {record['size']} != {len(text.encode('utf-8'))}")
    excerpt = record["excerpt"]
    if not excerpt["head"] or excerpt["omitted_bytes"] <= 0:
        problems.append("the model-facing excerpt omits nothing and is not an excerpt")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"status={record['status']} stored={record['size']} bytes omitted={record['excerpt']['omitted_bytes']}",
        evidence={"record": {key: record[key] for key in ("status", "size", "sha256", "relative_path")},
                  "problems": problems},
    )


@case(
    id="externalized-output.digest-correct",
    group="externalized-output",
    title="The recorded digest is the digest of the stored bytes",
    task="Externalize an output, re-hash the artifact and compare with the record.",
    expectation="The digests match and a tampered artifact is refused.",
    evaluation="Verify the artifact, then tamper with it and verify again.",
    evidence_required="Both digest verdicts.",
    layer="deterministic",
)
def external_digest(ctx: Ctx) -> Outcome:
    module, box, record, text = externalized_case_setup(ctx)
    verdict = module.ARTIFACTS.verify_artifact(record)
    path = Path(record["path"])
    original = path.read_bytes()
    path.write_bytes(original + b"tampered")
    tampered = module.ARTIFACTS.verify_artifact(record)
    path.write_bytes(original)
    restored = module.ARTIFACTS.verify_artifact(record)
    problems = []
    if not verdict["ok"]:
        problems.append(f"the freshly written artifact did not verify: {verdict}")
    if tampered["ok"]:
        problems.append("a tampered artifact verified")
    if not restored["ok"]:
        problems.append("the restored artifact did not verify")
    if record["sha256"] != hashlib.sha256(original).hexdigest():
        problems.append("the recorded digest is not the digest of the stored bytes")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"clean={verdict['ok']} tampered={tampered['ok']} restored={restored['ok']}",
        evidence={"sha256": record["sha256"], "problems": problems},
    )


@case(
    id="externalized-output.excerpt-correct",
    group="externalized-output",
    title="The excerpt is a head and tail of the real output",
    task="Externalize a numbered output and check the excerpt against the original.",
    expectation="The head starts the output, the tail ends it and the omitted byte count is exact.",
    evaluation="Compare the excerpt strings with the original and compute the omitted bytes.",
    evidence_required="The excerpt, the tail and the omitted byte count.",
    layer="deterministic",
)
def external_excerpt(ctx: Ctx) -> Outcome:
    module, box, record, text = externalized_case_setup(ctx)
    excerpt = record["excerpt"]
    encoded = text.encode("utf-8")
    problems = []
    if not text.startswith(excerpt["head"]):
        problems.append("the excerpt head is not the head of the output")
    if not text.endswith(excerpt["tail"]):
        problems.append("the excerpt tail is not the tail of the output")
    expected_omitted = len(encoded) - len(excerpt["head"].encode("utf-8")) - len(excerpt["tail"].encode("utf-8"))
    if excerpt["omitted_bytes"] != expected_omitted:
        problems.append(f"the omitted byte count {excerpt['omitted_bytes']} != {expected_omitted}")
    rendered = module.ARTIFACTS.render_for_model(record)
    if record["sha256"] not in rendered or record["relative_path"] not in rendered:
        problems.append("the model-facing block does not reference the artifact")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"head={len(excerpt['head'])} tail={len(excerpt['tail'])} omitted={excerpt['omitted_bytes']}",
        evidence={"excerpt": {key: excerpt[key] for key in ("excerpted", "omitted_bytes")}, "problems": problems},
    )


@case(
    id="externalized-output.full-artifact-retrievable",
    group="externalized-output",
    title="The complete artifact is retrievable and digest-checked",
    task="Retrieve the full artifact through the engine and through a broken reference.",
    expectation="The full text comes back for a good record and a missing artifact is refused.",
    evaluation="Retrieve the record, then retrieve a record pointing at a missing file.",
    evidence_required="The retrieved length and the refusal.",
    layer="deterministic",
)
def external_retrievable(ctx: Ctx) -> Outcome:
    module, box, record, text = externalized_case_setup(ctx)
    got = module.ARTIFACTS.retrieve(record)
    broken = dict(record)
    broken["path"] = str(Path(record["path"]).with_name("missing-artifact.log"))
    refused = module.ARTIFACTS.retrieve(broken)
    problems = []
    if not got["ok"] or got["text"] != text:
        problems.append("the full artifact was not retrievable")
    if refused["ok"]:
        problems.append("a missing artifact was accepted as evidence")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"retrieved={got.get('bytes')} bytes refused_missing={not refused['ok']}",
        evidence={"problems": problems, "refusal": refused["problems"]},
    )


@case(
    id="externalized-output.verification-reads-original-artifact",
    group="externalized-output",
    title="A verification can read the original full artifact",
    task="Externalize an output, record a verification against the artifact and re-hash it.",
    expectation="The verification is created at OBSERVED against the stored artifact and stays current.",
    evaluation="Externalize, verify the claim through the engine and refresh the freshness.",
    evidence_required="The verification record and the artifact verdict.",
    layer="deterministic",
)
def external_verification(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    record = module.ARTIFACTS.externalize(
        box.run_root, data="failure log\n" * 900, tool="shell", command="npm test", task_id="bench-S4B",
    )
    observer = make_execution(module, state, role="validator", adapter="fixture:observer")
    verification = module.VERIFICATION.create(
        state, subject="bench-S4B", claim="the command output was preserved", level="OBSERVED",
        method="re-hash the stored artifact", execution_id=observer["execution_id"],
        revision=REVISION, evidence=[{"path": record["path"]}], dependencies={"artifact": record["sha256"]},
    )
    freshness = module.VERIFICATION.freshness_of(verification, current={"artifact": record["sha256"]})
    stale = module.VERIFICATION.freshness_of(verification, current={"artifact": "00" * 32})
    problems = []
    if freshness["state"] != "CURRENT":
        problems.append(f"the verification is not current against the artifact: {freshness}")
    if stale["state"] != "STALE":
        problems.append("a changed artifact did not make the verification stale")
    if not module.ARTIFACTS.verify_artifact(record)["ok"]:
        problems.append("the artifact was not readable after verification")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"current={freshness['state']} changed={stale['state']} artifact={record['size']} bytes",
        evidence={"verification": verification["verification_id"], "problems": problems},
    )


@case(
    id="externalized-output.runtime-validation-externalizes-large-output",
    group="externalized-output",
    title="The runtime preserves a large validation output instead of keeping only its digest",
    task="Call the runtime's validation-output seam with a large and a small output and read the results.",
    expectation="The large output is stored in full with a reference and the small output is untouched.",
    evaluation="Call the runtime seam twice and inspect the artifact, the state collection and the small case.",
    evidence_required="The artifact, its digest and the returned fields.",
    layer="deterministic",
)
def external_runtime_seam(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    box.run_root.mkdir(parents=True, exist_ok=True)
    state = bench_state(box)
    large = "\n".join(f"FAIL src/spec-{index}.ts: expected 1 received 2" for index in range(1500))
    fields = module.externalize_validation_output(
        box.run_root, state, command={"command": "npm test", "id": "tests"}, stdout=large, stderr="",
    )
    small = module.externalize_validation_output(
        box.run_root, state, command={"command": "npm test", "id": "tests"}, stdout="ok\n", stderr="",
    )
    problems = []
    record = fields.get("stdout_artifact")
    if not record:
        problems.append("the large validation output was not externalized")
    else:
        stored = Path(box.run_root) / record["relative_path"]
        if not stored.is_file() or stored.read_text(encoding="utf-8") != large:
            problems.append("the stored validation artifact is not the complete output")
        if hashlib.sha256(large.encode("utf-8")).hexdigest() != record["sha256"]:
            problems.append("the recorded digest is not the digest of the output")
    if small:
        problems.append("a small output was externalized unnecessarily")
    if not state.get("artifacts"):
        problems.append("no artifact reference was recorded in the run state")
    if not fields.get("output_externalized"):
        problems.append("the externalization was not declared")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"stored={bool(record)} small_untouched={not small} references={len(state.get('artifacts') or [])}",
        evidence={"fields": {"output_externalized": fields.get("output_externalized", False)},
                  "problems": problems},
    )


# ========================================================== context economics


def candidate(path: Path, *, required=False, removable=False, bucket="project", kind="project",
              forbidden=False, exists=True) -> dict:
    return {
        "label": path.name, "path": str(path), "kind": kind, "bucket": bucket,
        "required": required, "removable": removable, "exists": exists, "forbidden": forbidden,
        "selectable": True, "selection_reason": "",
    }


@case(
    id="context-economics.repeated-identical-source-not-duplicated",
    group="context-economics",
    title="Repeated identical history content is measured as a duplicate, not re-delivered",
    task="Build a history with an exact duplicate and measure it, then compact it.",
    expectation="The duplicate is measured and the compacted active view carries it once.",
    evaluation="Measure the history, compact it and count the duplicate markers.",
    evidence_required="The economics figures and the compaction result.",
    layer="deterministic",
)
def context_duplicates(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    entries = [
        module.HISTORY.entry("conversation", "the same worker handoff text", turn=1, label="a"),
        module.HISTORY.entry("conversation", "the same worker handoff text", turn=2, label="b"),
        module.HISTORY.entry("tool_output", "different output", turn=2, label="c"),
    ]
    economics = module.HISTORY.history_economics(entries)
    compacted = module.HISTORY.compact(box.run_root, entries)
    active_lines = [row for row in compacted["active"] if not row.get("protected")]
    problems = []
    if economics["duplicate_groups"] != 1 or economics["duplicate_bytes"] <= 0:
        problems.append(f"the duplicate was not measured: {economics}")
    if compacted["duplicates_omitted"] != 1:
        problems.append("the duplicate was not omitted from the active view")
    if len(active_lines) != 2:
        problems.append(f"the active view carried {len(active_lines)} unprotected entries, not 2")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"duplicates={economics['duplicate_groups']} omitted={compacted['duplicates_omitted']}",
        evidence={"economics": economics, "problems": problems},
    )


@case(
    id="context-economics.forbidden-context-stays-forbidden",
    group="context-economics",
    title="A forbidden source is never delivered, cached or resurrected",
    task="Decide context for a forbidden source with a cache entry present and read the plan.",
    expectation="The source is omitted as FORBIDDEN_FOR_STAGE and the plan cannot add it back.",
    evaluation="Decide, build the plan and read the omission.",
    evidence_required="The decision rows and the plan.",
    layer="deterministic",
)
def context_forbidden(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    forbidden_path = box.write("source-code.ts", "export const x = 1;\n")
    box.run_root.mkdir(parents=True, exist_ok=True)
    cache_path = box.run_root / module.CONTEXT.CACHE_NAME
    cache_path.write_text(json.dumps({
        "schema_version": module.CONTEXT.CACHE_SCHEMA,
        "entries": {str(forbidden_path): {
            "source_sha256": "ab" * 32, "content_sha256": "cd" * 32, "size": 21, "mtime_ns": 1,
            "stage": "S5", "policy_version": module.CONTRACTS.POLICY_VERSION, "revision_hash": REVISION,
        }},
    }), encoding="utf-8")
    decision = module.CONTEXT.decide(
        state, stage="S5", candidates=[candidate(forbidden_path, bucket="canonical", forbidden=True)],
        run_root=box.run_root, revision_hash=REVISION,
    )
    plan = module.CONTEXT.plan(decision)
    problems = []
    if decision["decisions"][0]["reason"] != "FORBIDDEN_FOR_STAGE":
        problems.append(f"the forbidden source was not refused: {decision['decisions'][0]}")
    if str(forbidden_path) in plan["reuse"]:
        problems.append("the cache resurrected a forbidden source")
    if str(forbidden_path) in plan["omit"] and plan["omit"][str(forbidden_path)] != "FORBIDDEN_FOR_STAGE":
        problems.append("the omission reason was rewritten")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"reason={decision['decisions'][0]['reason']} reused={str(forbidden_path) in plan['reuse']}",
        evidence={"decision": decision, "plan": plan, "problems": problems},
    )


@case(
    id="context-economics.required-context-not-removed",
    group="context-economics",
    title="A required source is delivered even when a plan tries to omit it",
    task="Decide context for a required source and attempt an omission plan.",
    expectation="The required source is included and the plan carries no omission for it.",
    evaluation="Decide, build the plan and read the decision rows.",
    evidence_required="The decision row and the plan.",
    layer="deterministic",
)
def context_required(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    required = box.write("PROJECT.md", "# PROJECT\n")
    decision = module.CONTEXT.decide(
        state, stage="S3", candidates=[candidate(required, required=True)],
        run_root=box.run_root, revision_hash=REVISION,
    )
    plan = module.CONTEXT.plan(decision)
    problems = []
    if decision["decisions"][0]["decision"] != "included":
        problems.append(f"a required source was not included: {decision['decisions'][0]}")
    if str(required) in plan["omit"]:
        problems.append("the plan omits a required source")
    if decision["decisions"][0]["reason"] not in ("REQUIRED_BY_STAGE", "UNCHANGED_CACHED_INPUT"):
        problems.append(f"the inclusion reason is unexpected: {decision['decisions'][0]['reason']}")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"decision={decision['decisions'][0]['decision']} reason={decision['decisions'][0]['reason']}",
        evidence={"plan": plan, "problems": problems},
    )


@case(
    id="context-economics.cache-invalidation-on-source-change",
    group="context-economics",
    title="A changed source invalidates its cached hash",
    task="Reuse a cached source, change it and decide again.",
    expectation="The first decision reuses the cached hash; after the change the hash is re-derived.",
    evaluation="Decide twice with the file changed in between and compare the reasons.",
    evidence_required="Both decisions and the invalidations.",
    layer="deterministic",
)
def context_invalidates(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    box.run_root.mkdir(parents=True, exist_ok=True)
    path = box.write("PROJECT.md", "# PROJECT\n\nVersion one.\n")
    manifest = {"packet_id": "bench-S3", "packet_sha256": "ef" * 32, "project_baseline": {"head": REVISION},
                "sources": [{"path": str(path), "label": "PROJECT.md", "kind": "project", "delivered": True,
                             "source_sha256": "11" * 32, "content_sha256": "22" * 32}]}
    first = module.CONTEXT.decide(
        state, stage="S3", candidates=[candidate(path, required=True)],
        run_root=box.run_root, revision_hash=REVISION,
    )
    module.CONTEXT.update_cache(box.run_root, state, first, manifest, revision_hash=REVISION)
    second = module.CONTEXT.decide(
        state, stage="S3", candidates=[candidate(path, required=True)],
        run_root=box.run_root, revision_hash=REVISION,
    )
    path.write_text("# PROJECT\n\nVersion two!\n", encoding="utf-8")
    third = module.CONTEXT.decide(
        state, stage="S3", candidates=[candidate(path, required=True)],
        run_root=box.run_root, revision_hash=REVISION,
    )
    problems = []
    if first["decisions"][0]["reason"] != "REQUIRED_BY_STAGE":
        problems.append(f"the first decision did not derive a hash: {first['decisions'][0]}")
    if second["decisions"][0]["reason"] != "UNCHANGED_CACHED_INPUT":
        problems.append(f"the unchanged source was not cached: {second['decisions'][0]}")
    if third["decisions"][0]["reason"] == "UNCHANGED_CACHED_INPUT":
        problems.append("a changed source was served from the cache")
    if not third["cache"]["invalidated"]:
        problems.append("the invalidation was not recorded")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"first={first['decisions'][0]['reason']} second={second['decisions'][0]['reason']} "
               f"third={third['decisions'][0]['reason']}",
        evidence={"invalidated": third["cache"]["invalidated"], "problems": problems},
    )


# ================================================================= compaction


def history_entries(module):
    return [
        module.HISTORY.entry("task_state", "Task bench-S4B is at implementation, revision ab.", turn=1),
        module.HISTORY.entry("unresolved_work", "The footer contrast still fails the rubric.", turn=2),
        module.HISTORY.entry("decision", "Chose the CMS-free static export.", turn=2),
        module.HISTORY.entry("authorization", "G1 approved by the operator on 2026-01-01.", turn=3),
        module.HISTORY.entry("evidence_ref", "evidence/validation.json sha256 1111", turn=3),
        module.HISTORY.entry("failed_approach", "The carousel rewrite broke the scope check.", turn=4),
        module.HISTORY.entry("tool_output", "npm test output line\n" * 400, turn=4),
        module.HISTORY.entry("summary", "Earlier summary of the planning conversation.", turn=5),
        module.HISTORY.entry("conversation", "planning chatter", turn=5),
    ]


@case(
    id="compaction.current-state-preserved",
    group="compaction",
    title="Compaction carries the current task state verbatim",
    task="Compact a history and read the active view for the task state.",
    expectation="The task-state entry and the revision entry are carried verbatim.",
    evaluation="Compact and compare the protected entries with the originals.",
    evidence_required="The active view and the archive.",
    layer="deterministic",
)
def compaction_state(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    entries = history_entries(module)
    result = module.HISTORY.compact(box.run_root, entries)
    by_kind = {row["kind"]: row for row in result["active"]}
    original = {row["kind"]: row for row in entries}
    problems = []
    for kind in ("task_state", "unresolved_work", "decision", "authorization", "evidence_ref", "failed_approach"):
        row = by_kind.get(kind)
        if row is None or not row.get("protected"):
            problems.append(f"{kind} was not carried as a protected entry")
        elif row.get("text") != original[kind]["text"]:
            problems.append(f"{kind} was paraphrased")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"protected={result['protected_entries']} structured={result['structured_entries']}",
        evidence={"kinds": sorted(by_kind), "problems": problems},
    )


@case(
    id="compaction.unresolved-work-preserved",
    group="compaction",
    title="Compaction cannot drop unresolved work or a protected decision",
    task="Attempt an unsafe compaction plan and read the refusal.",
    expectation="A plan that would omit a protected entry is refused.",
    evaluation="Call the guard with a plan that drops the unresolved-work entry.",
    evidence_required="The refusal and the plan.",
    layer="deterministic",
)
def compaction_unresolved(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    entries = history_entries(module)
    unsafe = [dict(item) for item in entries]
    for index, item in enumerate(unsafe):
        if item["kind"] == "unresolved_work":
            unsafe[index]["decision"] = "omit"
    plan = {"omit": ["h1"], "archive_path": str(box.run_root / "history" / "x.jsonl")}
    problems = module.HISTORY.compaction_problems(unsafe, plan)
    safe = module.HISTORY.compaction_problems(entries, {"omit": [], "archive_digest": "ab" * 32})
    return Outcome(
        status="pass" if problems and not safe else "fail",
        actual=f"unsafe_refused={bool(problems)} safe_accepted={not safe}",
        evidence={"problems": problems, "safe_problems": safe},
    )


@case(
    id="compaction.full-history-retrievable",
    group="compaction",
    title="The complete original history stays retrievable after compaction",
    task="Compact a history, retrieve the archive and compare it with the originals.",
    expectation="Every original entry comes back from the archive and a tampered archive is refused.",
    evaluation="Compact, retrieve, compare and tamper.",
    evidence_required="The retrieved entries and the archive digest.",
    layer="deterministic",
)
def compaction_retrievable(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    entries = history_entries(module)
    result = module.HISTORY.compact(box.run_root, entries)
    got = module.HISTORY.retrieve_history(result)
    archive = Path(result["archive_path"])
    original = archive.read_bytes()
    archive.write_bytes(original + b"\n")
    tampered = module.HISTORY.retrieve_history(result)
    archive.write_bytes(original)
    problems = []
    if not got["ok"] or len(got["entries"]) != len(entries):
        problems.append(f"the archive did not return every entry: {len(got.get('entries', []))}")
    if got["ok"] and [row["digest"] for row in got["entries"]] != [row["digest"] for row in entries]:
        problems.append("the archived entries differ from the originals")
    if tampered["ok"]:
        problems.append("a tampered archive was accepted")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"entries={len(got.get('entries', []))} tampered_refused={not tampered['ok']}",
        evidence={"archive_digest": result["archive_digest"], "problems": problems},
    )


@case(
    id="compaction.stale-tool-noise-omitted-from-active-view",
    group="compaction",
    title="Bulk tool noise is structured out of the active view",
    task="Compact a history with a large tool output and read the active entry.",
    expectation="The tool output becomes one structured line with its digest while remaining archived.",
    evaluation="Compact and inspect the tool-output entry.",
    evidence_required="The active entry, its digest and the archive.",
    layer="deterministic",
)
def compaction_noise(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    entries = history_entries(module)
    result = module.HISTORY.compact(box.run_root, entries)
    noisy = next(row for row in result["active"] if row["kind"] == "tool_output")
    archived = next(row for row in entries if row["kind"] == "tool_output")
    rendered = module.HISTORY.render_active(result)
    problems = []
    if noisy.get("text"):
        problems.append("the tool output was carried verbatim in the active view")
    if noisy.get("first_line") != archived["text"].splitlines()[0][:120]:
        problems.append("the structured line does not carry the first line")
    if noisy["digest"] != archived["digest"]:
        problems.append("the structured line lost the digest")
    archived_rows = json.loads("[" + ",".join(
        line for line in Path(result["archive_path"]).read_text(encoding="utf-8").splitlines() if line.strip()
    ) + "]")
    if not any(row.get("digest") == archived["digest"] and row.get("text") == archived["text"]
               for row in archived_rows):
        problems.append("the archive does not contain the full tool output")
    if noisy["bytes"] != archived["bytes"]:
        problems.append("the measured entry size changed")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"active_bytes={len(rendered.encode('utf-8'))} original_bytes={archived['bytes']}",
        evidence={"structured": {key: noisy.get(key) for key in ("kind", "bytes", "digest", "first_line")},
                  "problems": problems},
    )


# =========================================================== decision economics


@case(
    id="decision-economics.independent-questions-share-state",
    group="decision-economics",
    title="Independent questions share one state and one request",
    task="Evaluate a batch of two independent questions and read the economics view.",
    expectation="One provider call, two decisions, one shared state digest and no dependency problems.",
    evaluation="Evaluate the batch and read the decision economics.",
    evidence_required="The batch record and the economics row.",
    layer="deterministic",
)
def decisions_shared_state(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = module.DECISIONS.providers.DeterministicProvider(
        script={"shape": {"answer": "square"}, "tone": {"answer": "calm"}},
    )
    projection = module.DECISIONS.batch.project(entries={"brief": {"shape": "square", "tone": "calm"}})
    batch = module.DECISIONS.batch.evaluate(
        state, questions=[
            module.DECISIONS.contracts.DecisionQuestion(
                question_id="shape", instructions="Pick the shape.", primitive="ChoiceDecision",
                options=("square", "round"),
            ),
            module.DECISIONS.contracts.DecisionQuestion(
                question_id="tone", instructions="Pick the tone.", primitive="ChoiceDecision",
                options=("calm", "loud"),
            ),
        ],
        projection=projection, provider=provider, task_id="bench-S4B",
    )
    economics = module.ECONOMICS.decision_economics(state, task_id="bench-S4B")
    problems = []
    if batch["status"] != "answered" or len(batch["results"]) != 2:
        problems.append(f"the batch did not answer both questions: {batch['status']}")
    if economics["totals"]["requests"] != 1:
        problems.append(f"the batch used {economics['totals']['requests']} requests, not 1")
    if economics["totals"]["state_bytes"] <= 0:
        problems.append("the shared state size was not measured")
    digests = {row["state_digest"] for row in economics["batches"]}
    if len(digests) != 1:
        problems.append("the questions did not share one state digest")
    if economics["batches"][0]["dependency_problems"]:
        problems.append("independent questions reported dependency problems")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"status={batch['status']} questions=2 requests={economics['totals']['requests']}",
        evidence={"economics": economics, "problems": problems},
    )


@case(
    id="decision-economics.dependent-decision-requires-new-step",
    group="decision-economics",
    title="A dependent question is refused inside one batch and planned as a second step",
    task="Declare a dependency between two questions and read the guard and the plan.",
    expectation="The guard refuses the dependent batch; the planner puts the dependent question in step two.",
    evaluation="Call the dependency guard and the batch planner.",
    evidence_required="The guard's problems and the planned steps.",
    layer="deterministic",
)
def decisions_dependency(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    questions = [
        {"question_id": "framework", "primitive": "ChoiceDecision"},
        {"question_id": "routing", "primitive": "ChoiceDecision"},
    ]
    problems = module.ECONOMICS.batch_dependency_problems(
        questions, depends_on={"routing": ["framework"]},
    )
    plan = module.ECONOMICS.plan_batches(questions, depends_on={"routing": ["framework"]})
    cycle = ""
    try:
        module.ECONOMICS.plan_batches(
            [{"question_id": "a"}, {"question_id": "b"}], depends_on={"a": ["b"], "b": ["a"]},
        )
    except module.CONTRACTS.ContractError as exc:
        cycle = str(exc)
    failures = []
    if not problems:
        failures.append("a dependent question was accepted inside one batch")
    if plan["batches"] != 2 or plan["steps"][0] != ["framework"]:
        failures.append(f"the planner did not separate the dependent question: {plan['steps']}")
    if not cycle:
        failures.append("a dependency cycle was accepted")
    return Outcome(
        status="pass" if not failures else "fail",
        actual=f"refused={bool(problems)} batches={plan['batches']} cycle_refused={bool(cycle)}",
        evidence={"problems": problems, "plan": plan, "cycle": cycle, "failures": failures},
    )


@case(
    id="decision-economics.usage-attribution-correct",
    group="decision-economics",
    title="A batch's usage is attributed to the task and never invented",
    task="Evaluate a batch with no measured usage and read the attribution.",
    expectation="The batch is attributed to the task, its usage is unmeasured and no cost is invented.",
    evaluation="Evaluate, read the economics rows and compare with the recorded usage.",
    evidence_required="The batch row, the attribution and the measured flag.",
    layer="deterministic",
)
def decisions_attribution(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    box = project_box(ctx)
    state = bench_state(box)
    provider = module.DECISIONS.providers.DeterministicProvider(script={"shape": {"answer": "square"}})
    projection = module.DECISIONS.batch.project(entries={"brief": "square"})
    module.DECISIONS.batch.evaluate(
        state, questions=[module.DECISIONS.contracts.DecisionQuestion(
            question_id="shape", instructions="Pick the shape.", primitive="ChoiceDecision",
            options=("square", "round"),
        )],
        projection=projection, provider=provider, task_id="bench-S4B",
    )
    other = module.ECONOMICS.decision_economics(state, task_id="other-task")
    economics = module.ECONOMICS.decision_economics(state, task_id="bench-S4B")
    problems = []
    if economics["totals"]["batches"] != 1 or other["totals"]["batches"] != 0:
        problems.append("the batch was attributed to the wrong task")
    row = economics["batches"][0]
    if row["usage_measured"]:
        problems.append("usage was claimed for a batch that measured none")
    if row["usage"]:
        problems.append(f"usage was invented: {row['usage']}")
    if not row["results"] or row["results"][0]["status"] != "answered":
        problems.append("the answered result was not attributed to the task")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"batches={economics['totals']['batches']} measured={row['usage_measured']} other={other['totals']['batches']}",
        evidence={"economics": economics, "problems": problems},
    )


# ======================================================= orchestration economics


@case(
    id="orchestration-economics.simple-path-avoids-unnecessary-worker",
    group="orchestration-economics",
    title="A simple low-stakes task keeps the short path with validation",
    task="Derive the path for a low-stakes mechanical task and read the retained steps.",
    expectation="The simple path is chosen, decision and review are skipped and validation is retained.",
    evaluation="Call the planner and read the retained and skipped steps.",
    evidence_required="The plan and the verification guard.",
    layer="deterministic",
)
def orchestration_simple(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    plan = module.ORCHESTRATION.path_plan(stakes="LOW", difficulty="LOW", required_capabilities=["edit"])
    guard = module.ORCHESTRATION.require_verification_retained(plan)
    problems = []
    if plan["path"] != module.ORCHESTRATION.PATH_FAST:
        problems.append(f"a simple task did not take the fast path: {plan}")
    if "validation" not in plan["retained"] or guard:
        problems.append(f"validation was not retained: {guard}")
    if "decision" in plan["retained"] or "review" in plan["retained"]:
        problems.append("the simple path kept an unnecessary step")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"path={plan['path']} retained={plan['retained']}",
        evidence={"plan": plan, "guard": guard, "problems": problems},
    )


@case(
    id="orchestration-economics.high-stakes-path-retains-verification",
    group="orchestration-economics",
    title="A high-stakes design task keeps review, validation and acceptance",
    task="Derive the path for a high-stakes design task and read the retained steps.",
    expectation="The complex path retains decision, routing, review, validation and human acceptance.",
    evaluation="Call the planner and compare the retained steps with the obligations.",
    evidence_required="The plan and its reasons.",
    layer="deterministic",
)
def orchestration_complex(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    plan = module.ORCHESTRATION.path_plan(
        stakes="HIGH", difficulty="HIGH", design_required=True, review_required=True,
        human_acceptance_required=True,
    )
    problems = []
    for step in ("review", "validation", "human-acceptance"):
        if step not in plan["retained"]:
            problems.append(f"the complex path dropped {step}")
    if plan["path"] != module.ORCHESTRATION.PATH_COMPLEX:
        problems.append(f"a high-stakes design task did not take the complex path: {plan}")
    if not plan["verification_retained"] or module.ORCHESTRATION.require_verification_retained(plan):
        problems.append("the complex path did not assert verification retention")
    if len(plan["reasons"]) < 3:
        problems.append("the path did not record why it was lengthened")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"path={plan['path']} retained={plan['retained']}",
        evidence={"plan": plan, "problems": problems},
    )


@case(
    id="orchestration-economics.cost-cannot-bypass-policy",
    group="orchestration-economics",
    title="A cheaper path cannot drop a required capability or a required review",
    task="Ask for a fast path with a required capability and with review required, then read the refusals.",
    expectation="Neither request yields the simple path and the verification guard refuses a crafted plan.",
    evaluation="Call the planner with each obstacle and check the guard on a hand-built plan.",
    evidence_required="Both plans and the guard problems.",
    layer="deterministic",
)
def orchestration_cost_guard(ctx: Ctx) -> Outcome:
    module = runtime(ctx)
    capability_plan = module.ORCHESTRATION.path_plan(
        stakes="LOW", required_capabilities=["rendered-evidence"],
    )
    review_plan = module.ORCHESTRATION.path_plan(stakes="LOW", review_required=True)
    crafted = {"path": "simple", "retained": ["worker"], "verification_retained": False}
    guard = module.ORCHESTRATION.require_verification_retained(crafted)
    offload = module.TOOLING.required_capability_problems(["rendered-evidence"], ["core"])
    problems = []
    if capability_plan["path"] == module.ORCHESTRATION.PATH_FAST:
        problems.append("a capability-requiring task was allowed the fast path")
    if review_plan["path"] == module.ORCHESTRATION.PATH_FAST:
        problems.append("a review-requiring task was allowed the fast path")
    if not guard:
        problems.append("a plan that dropped validation was accepted")
    if not offload:
        problems.append("offloading was allowed to hide a required capability")
    return Outcome(
        status="pass" if not problems else "fail",
        actual=f"capability_path={capability_plan['path']} review_path={review_plan['path']} "
               f"guard={len(guard)} offload={len(offload)}",
        evidence={"capability_plan": capability_plan, "review_plan": review_plan, "guard": guard,
                  "offload": offload, "problems": problems},
    )
