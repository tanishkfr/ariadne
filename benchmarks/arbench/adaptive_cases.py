"""AR-202 adaptive-execution benchmark cases.

These cases drive the same runtime an operator drives. Nothing here calls a
model, reaches the network, or writes inside a repository: every fixture lives
in a sandbox under ``--work-root``.

Groups:

    adaptive-context         what the packet included, omitted, reused and why
    routing                  the executed routing decision and its refusals
    execution-identity       engine-bound provenance for results and reviews
    recovery                 safe resolution of known interruption states
    evidence-continuation    the S4A/S4B/S5 continuation evidence requirements

Statuses keep the AR-200 semantics: ``pass`` is a satisfied integrity
expectation, ``fail`` is a real defect, ``observed`` is a recorded probe,
``error`` means the harness could not evaluate the case.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .cases import Ctx, Outcome, case, exit_outcome
from . import fixtures as F


def _state(box) -> dict:
    return json.loads((box.run_root / "ariadne-run.json").read_text(encoding="utf-8"))


def _write_state(box, state: dict) -> None:
    (box.run_root / "ariadne-run.json").write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _latest(state: dict, name: str) -> dict:
    values = state.get(name)
    if isinstance(values, list) and values and isinstance(values[-1], dict):
        return values[-1]
    return {}


def _decision_entry(decision: dict, needle: str) -> dict:
    for item in decision.get("decisions", []) or []:
        if needle in str(item.get("path", "")):
            return item
    return {}


def _events(box) -> list[dict]:
    path = box.run_root / "engine-events.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ========================================================= group: adaptive-context

@case(id="adaptive-context.required-sources-and-reasons", group="adaptive-context",
      title="Every candidate source has an inclusion decision with a machine-readable reason",
      task="Prepare S3 and read the recorded context decision beside the delivered manifest.",
      expectation="Required sources are included with reasons; each decision is structurally valid and bound to the packet.",
      evaluation="Compare the state's context decision with the manifest's delivered sources.",
      evidence_required="Context decision record, manifest context_decision block, packet section list.",
      layer="deterministic")
def adaptive_context_required(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    runtime = ctx.repo.module("ariadne.py")
    state = _state(box)
    decision = _latest(state, "context_decisions")
    manifest = box.manifest()
    delivered = [item["path"] for item in manifest["sources"] if item.get("delivered", True)]
    required = [item for item in decision.get("decisions", []) if item.get("bucket") == "project"]
    problems = runtime.CONTRACTS.context_decision_problems(decision)
    reasons_ok = all(item.get("reason") for item in decision.get("decisions", []))
    bound = str((manifest.get("context_decision") or {}).get("decision_id", "")) == str(
        decision.get("decision_id", ""))
    ok = (
        not problems
        and reasons_ok
        and bound
        and required
        and all(item.get("decision") == "included" for item in required)
        and all(str(item.get("path")) in delivered for item in required)
        and decision.get("included", 0) >= 1
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            f"{decision.get('included')} included, {decision.get('omitted')} omitted, "
            f"{len(required)} required project sources bound to packet "
            f"{manifest.get('packet_id')}"
        ) if ok else f"decision={decision.get('decision_id')} problems={problems} bound={bound}",
        {
            "decision": decision,
            "delivered": delivered,
            "manifest_decision_id": (manifest.get("context_decision") or {}).get("decision_id"),
            "problems": problems,
        },
        {"sources_considered": len(decision.get("decisions", [])), "sources_included": decision.get("included", 0),
         "model_calls": 0},
    )


@case(id="adaptive-context.omitted-optional-source", group="adaptive-context",
      title="An optional source the task does not need is omitted with a reason",
      task="Prepare S3 for a run that declares it does not require creative evidence.",
      expectation="The optional creative ledger is omitted as irrelevant, required sources are unchanged.",
      evaluation="Read the omission reason and confirm the ledger is absent from the packet.",
      evidence_required="Decision entry, packet body, delivered source list.",
      layer="deterministic")
def adaptive_context_omitted(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    state = _state(box)
    state["creative_evidence_required"] = False
    _write_state(box, state)
    F.to_s3(ctx.repo, box)
    state = _state(box)
    decision = _latest(state, "context_decisions")
    manifest = box.manifest()
    packet = box.packet_text()
    entry = _decision_entry(decision, "creative-evidence.json")
    required_still_delivered = all(
        item.get("decision") == "included"
        for item in decision.get("decisions", [])
        if item.get("required")
    )
    ok = (
        entry.get("decision") == "omitted"
        and entry.get("reason") == "IRRELEVANT_TO_TASK"
        and "creative-evidence.json" not in " ".join(
            item["path"] for item in manifest["sources"] if item.get("delivered", True))
        and "BEGIN .ariadne/creative-evidence.json" not in packet
        and required_still_delivered
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "the optional creative ledger was omitted as irrelevant and every required source was still "
            "delivered"
        ) if ok else f"entry={entry} required_delivered={required_still_delivered}",
        {"decision_entry": entry, "delivered": [item["label"] for item in manifest["sources"]
                                                if item.get("delivered", True)]},
        {"bytes": len(packet), "model_calls": 0},
    )


@case(id="adaptive-context.cache-reuse-on-unchanged-retry", group="adaptive-context",
      title="A retry with unchanged canonical inputs reuses recorded source hashes",
      task="Prepare S4B, then escalate to a second attempt without changing any delivered source.",
      expectation="The second decision records cache hits and the packet still verifies.",
      evaluation="Read the second context decision and the cache-hit events; re-verify the packet.",
      evidence_required="Context decision cache block, engine events, packet verification.",
      layer="deterministic")
def adaptive_context_cache_reuse(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="blocked")
    ctx.repo.cli("advance", "--run-root", str(box.run_root))
    first = _latest(_state(box), "context_decisions")
    result = ctx.repo.cli("prepare-next", "--run-root", str(box.run_root), "--escalate")
    state = _state(box)
    second = _latest(state, "context_decisions")
    hits = int((second.get("cache") or {}).get("hits", 0) or 0)
    hits_events = [item for item in _events(box) if item.get("type") == "context_cache_hit"]
    reused = [item for item in second.get("decisions", []) if item.get("reason") == "UNCHANGED_CACHED_INPUT"]
    packet_ok = ctx.repo.module("ariadne.py").TRANSPORT.verify_packet(box.current_packet()) == []
    ok = (
        result.returncode == 0
        and hits >= 1
        and bool(reused)
        and bool(hits_events)
        and packet_ok
        and second.get("decision_id") != first.get("decision_id")
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            f"the retry decision reused {hits} cached source hash(es) and the packet still verifies"
        ) if ok else f"exit={result.returncode} hits={hits} reused={len(reused)} verify={packet_ok}",
        {
            "first_decision": first.get("decision_id"),
            "second_decision": second.get("decision_id"),
            "cache": second.get("cache"),
            "reused_paths": [item.get("path") for item in reused],
            "cache_hit_events": len(hits_events),
        },
        {"cache_hits": hits, "sources_considered": len(second.get("decisions", [])), "model_calls": 0},
    )


@case(id="adaptive-context.semantic-edit-invalidates-cache", group="adaptive-context",
      title="An edited source is re-derived and the stale hash is not reused",
      task="Prepare S4B, edit a delivered project source, then prepare the next attempt.",
      expectation="The edited source is recorded as invalidated and the packet carries the new hash.",
      evaluation="Compare the recorded invalidation, the packet header hash and the current file hash.",
      evidence_required="Invalidation event, packet source header, file hash.",
      layer="deterministic")
def adaptive_context_semantic_edit(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="blocked")
    ctx.repo.cli("advance", "--run-root", str(box.run_root))
    box.append("AGENTS.md", "\n<!-- adaptive-context benchmark edit -->\n")
    edited_hash = box.sha256("AGENTS.md")
    result = ctx.repo.cli("prepare-next", "--run-root", str(box.run_root), "--escalate")
    state = _state(box)
    decision = _latest(state, "context_decisions")
    manifest = box.manifest()
    source = next((item for item in manifest["sources"]
                   if str(item.get("path", "")).endswith("AGENTS.md")), {})
    invalidated = [item for item in _events(box) if item.get("type") == "context_invalidated"]
    ok = (
        result.returncode == 0
        and bool(invalidated)
        and source.get("source_sha256") == edited_hash
        and not any(item.get("reason") == "UNCHANGED_CACHED_INPUT"
                    for item in decision.get("decisions", []) if "AGENTS.md" in str(item.get("path")))
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "the edited source invalidated its cache entry and the packet carries a freshly derived hash"
        ) if ok else f"exit={result.returncode} invalidations={len(invalidated)} header={source.get('source_sha256')}",
        {
            "invalidation_events": invalidated,
            "packet_source_sha256": source.get("source_sha256"),
            "current_file_sha256": edited_hash,
        },
        {"invalidations": len(invalidated), "model_calls": 0},
    )


@case(id="adaptive-context.forbidden-source-never-delivered", group="adaptive-context",
      title="Adaptive context cannot surface a forbidden source at S5",
      task="Reach the isolated review boundary on a run with a populated context cache.",
      expectation="S5 delivers only the canonical pair; no cached or project source is included.",
      evaluation="Inspect delivered labels, the decision record and the packet body.",
      evidence_required="Delivered labels, decision entries, packet inspection.",
      layer="deterministic")
def adaptive_context_forbidden(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    result = F.prepare_s5(ctx.repo, box)
    state = _state(box)
    decision = _latest(state, "context_decisions")
    manifest = box.manifest()
    packet = box.packet_text()
    delivered = [item["label"] for item in manifest["sources"] if item.get("delivered", True)]
    forbidden_present = [
        token for token in ("PROJECT.md", "DESIGN.md", "HANDOFF.md", "AGENTS.md", "QA.md", "creative-operations.json")
        if token in delivered or f"BEGIN {token}" in packet
    ]
    included_kinds = {item.get("kind") for item in decision.get("decisions", [])
                      if item.get("decision") == "included"}
    ok = (
        result.returncode == 0
        and delivered == ["current S5 prompt block", "EVALUATION-RUBRICS.md"]
        and not forbidden_present
        and included_kinds <= {"canonical-prompt", "canonical"}
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "the review boundary delivered only the canonical pair and no cached project source"
        ) if ok else f"delivered={delivered} forbidden_present={forbidden_present}",
        {"delivered": delivered, "included_kinds": sorted(included_kinds),
         "decision_id": decision.get("decision_id"), "forbidden_present": forbidden_present},
        {"sources_included": decision.get("included", 0), "model_calls": 0},
    )


@case(id="adaptive-context.preparation-measurements", group="adaptive-context",
      title="Measured preparation, decision and detection cost (observed, never judged)",
      task="Repeat a deterministic packet preparation with and without an adaptive plan and cache reuse.",
      expectation="Recorded numbers only: medians and ranges for preparation, decisions and detection.",
      evaluation="No pass/fail judgement; the case reports measured medians and ranges.",
      evidence_required="Timing samples, delivered bytes, source counts, cache-hit bytes.",
      layer="measurement")
def adaptive_measurements(ctx: Ctx) -> Outcome:
    import statistics
    import time as _time

    from arbench.driver import Result

    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    runtime = ctx.repo.module("ariadne.py")
    transport = runtime.TRANSPORT
    context = runtime.CONTEXT
    state = _state(box)
    project = Path(state["project"])
    parent = str(box.packets()[0]["path"])
    measurements = box.root / "measurements"
    measurements.mkdir(parents=True, exist_ok=True)

    def namespace(index: int, output: Path):
        return runtime.transport_namespace(
            stage="S3", project=str(project), output=str(output),
            packet_id=f"measure-S3-{index}", parent=parent, retry=True,
            provider="benchmark-fixture", worker_role=None, references_file=None,
            references_text=None, restart_context=None, motion="no", assets="no",
            target=None, lenses=None, synthetic_validation=False,
            request=state.get("request"),
        )

    def timed_prepare(index: int, *, plan_decision=None) -> tuple[float, dict]:
        output = measurements / f"packet-{index}"
        namespace_value = namespace(index, output)
        context_plan = context.plan(plan_decision) if plan_decision else None
        started = _time.perf_counter()
        transport.prepare(namespace_value, context_plan=context_plan)
        elapsed = (_time.perf_counter() - started) * 1000.0
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        return elapsed, manifest

    def summarise(samples: list[float]) -> dict:
        if not samples:
            return {}
        return {
            "median_ms": round(statistics.median(samples), 3),
            "min_ms": round(min(samples), 3),
            "max_ms": round(max(samples), 3),
            "samples_ms": [round(item, 3) for item in samples],
        }

    plain_samples: list[float] = []
    hit_samples: list[float] = []
    delivered = {}
    for index in range(5):
        elapsed, manifest = timed_prepare(index)
        plain_samples.append(elapsed)
        delivered = manifest
    # Prime the cache from a real delivery, then repeat with a plan that reuses it.
    primer_output = measurements / "packet-primer"
    primer_namespace = namespace(9, primer_output)
    primer_candidates = transport.plan_sources("S3", project, primer_namespace)
    primer_decision = context.decide(state, stage="S3", candidates=primer_candidates,
                                     run_root=box.run_root, revision_hash="")
    primer_elapsed, primer_manifest = timed_prepare(9, plan_decision=primer_decision)
    context.update_cache(box.run_root, state, context.finalise(primer_decision, primer_manifest),
                         primer_manifest)
    first_hit_decision = None
    hit_manifest = {}
    for index in range(10, 15):
        output = measurements / f"packet-{index}"
        namespace_value = namespace(index, output)
        candidates = transport.plan_sources("S3", project, namespace_value)
        decision = context.decide(state, stage="S3", candidates=candidates,
                                  run_root=box.run_root, revision_hash="")
        if first_hit_decision is None:
            first_hit_decision = decision
        elapsed, hit_manifest = timed_prepare(index, plan_decision=decision)
        hit_samples.append(elapsed)
    cached_bytes = sum(
        int(Path(str(item["path"])).stat().st_size)
        for item in hit_manifest.get("sources", [])
        if item.get("hashed_from") == "cache" and Path(str(item.get("path", ""))).is_file()
    )
    cache_hits = int(((first_hit_decision or {}).get("cache") or {}).get("hits", 0) or 0)
    cache_misses = int(((first_hit_decision or {}).get("cache") or {}).get("misses", 0) or 0)
    sources_included = len([item for item in delivered.get("sources", []) if item.get("delivered", True)])
    packet_bytes = len((measurements / "packet-10" / "packet.txt").read_text(encoding="utf-8"))

    routing_samples: list[float] = []
    context_samples: list[float] = []
    characterisation = runtime.ROUTING.characterize(
        state, project=project, stage="S4B", task_id="measure-S4B", transport=transport,
    )
    candidates = transport.plan_sources("S3", project, namespace(200, measurements / "packet-200"))
    for _ in range(50):
        started = _time.perf_counter()
        runtime.ROUTING.route(state, stage="S4B", characterisation=characterisation,
                              task_id="measure-S4B", declared_role="bulk")
        routing_samples.append((_time.perf_counter() - started) * 1000.0)
        started = _time.perf_counter()
        context.decide(state, stage="S3", candidates=candidates, run_root=box.run_root,
                       revision_hash="")
        context_samples.append((_time.perf_counter() - started) * 1000.0)
    recovery_samples: list[float] = []
    for _ in range(10):
        started = _time.perf_counter()
        runtime.RECOVERY.detect(box.run_root, state)
        recovery_samples.append((_time.perf_counter() - started) * 1000.0)

    evidence = {
        "prepare_without_plan": summarise(plain_samples),
        "prepare_with_plan_cache_hit": summarise(hit_samples),
        "sources_included": sources_included,
        "packet_bytes": packet_bytes,
        "cached_source_hashes_reused": cache_hits,
        "cache_misses_on_first_hit_run": cache_misses,
        "cached_source_bytes_not_rehashed": cached_bytes,
        "routing_decision": summarise(routing_samples),
        "context_decision": summarise(context_samples),
        "recovery_detection": summarise(recovery_samples),
        "note": (
            "medians of repeated deterministic preparations in one sandbox; host contention can move "
            "absolute milliseconds, so compare the medians and the ranges, not a single sample"
        ),
    }
    return Outcome(
        "observed",
        (
            f"prepare median {evidence['prepare_without_plan']['median_ms']} ms without a plan, "
            f"{evidence['prepare_with_plan_cache_hit']['median_ms']} ms with a cache-hit plan; "
            f"{cache_hits} source hash(es) reused ({cached_bytes} bytes not re-hashed); "
            f"routing decision median {evidence['routing_decision']['median_ms']} ms"
        ),
        evidence,
        {
            "model_calls": 0,
            "repetitions": 5,
            "packet_bytes": packet_bytes,
            "sources_included": sources_included,
        },
    )


# ===================================================================== routing

@case(id="routing.light-task-records-sufficient-route", group="routing",
      title="A low-difficulty task routes to the sufficient light strategy",
      task="Prepare the S4B boundary for a small typographic experiment.",
      expectation="The routing decision selects the declared bulk role and records it as sufficient.",
      evaluation="Read the recorded routing decision and the packet's worker contract.",
      evidence_required="Routing decision record, packet worker role, engine events.",
      layer="deterministic")
def routing_light_task(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    state = _state(box)
    decision = _latest(state, "routing_decisions")
    manifest = box.manifest()
    characterisation = _latest(state, "characterisations")
    route_events = [item for item in _events(box) if item.get("type") == "route_selected"]
    ok = (
        decision.get("status") == "selected"
        and decision.get("chosen", {}).get("id") == "bulk"
        and decision.get("chosen", {}).get("capability_verdict") == "sufficient"
        and decision.get("rule") == "declared-default"
        and manifest["worker"]["role"] == "bulk"
        and bool(route_events)
        and characterisation.get("difficulty", {}).get("value") in ("LOW", "UNKNOWN")
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            f"the route selected {decision.get('chosen', {}).get('id')} "
            f"({decision.get('chosen', {}).get('capability_verdict')}) by rule {decision.get('rule')}"
        ) if ok else f"status={decision.get('status')} chosen={decision.get('chosen')} role={manifest['worker']['role']}",
        {"routing": decision, "characterisation_difficulty": characterisation.get("difficulty"),
         "worker_role": manifest["worker"]["role"], "route_events": len(route_events)},
        {"candidates": len(decision.get("candidates", [])), "model_calls": 0},
    )


@case(id="routing.heavy-task-marks-declared-role-insufficient", group="routing",
      title="A high-difficulty, high-stakes task records that the declared role is insufficient",
      task="Start a run whose request declares a production authentication migration, then prepare S4B.",
      expectation="Characterisation raises difficulty/stakes and the route records the missing capability.",
      evaluation="Read the characterisation, the excluded candidate and the chosen verdict.",
      evidence_required="Characterisation record, routing decision exclusions.",
      layer="deterministic")
def routing_heavy_task(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box,
               request="Migrate the production authentication schema for live users without downtime.")
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    F.lock_g1(box, ctx.repo)
    F.approve_s3_and_reach_s4a(ctx.repo, box)
    F.write_handoff(box, ctx.fixtures)
    box.write("AGENTS.md", F.agents_md("S4", "G1", "prompts/build-kickoff.md"))
    ctx.repo.cli("record-result", "--run-root", str(box.run_root), "--status", "complete",
                 "--provider", "benchmark-fixture", "--model", "none",
                 "--summary", "Implementation handoff complete",
                 "--file", "HANDOFF.md", "--file", "AGENTS.md")
    F.record_skill_evidence(ctx.repo, box, skill="implementation-planning", output_relative="HANDOFF.md",
                            result="The handoff became the bounded build context.",
                            events_name="planning-events.json")
    result = F.clear_preflight_and_reach_s4b(ctx.repo, box)
    state = _state(box)
    decision = _latest(state, "routing_decisions")
    characterisation = _latest(state, "characterisations")
    excluded = [item for item in decision.get("exclusions", []) if item.get("id") == "bulk"]
    ok = (
        result.returncode == 0
        and characterisation.get("difficulty", {}).get("value") == "HIGH"
        and characterisation.get("stakes", {}).get("value") == "HIGH"
        and decision.get("status") == "selected"
        and decision.get("chosen", {}).get("capability_verdict") == "insufficient"
        and "implementation-repair" in decision.get("chosen", {}).get("missing_capabilities", [])
        and bool(excluded)
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "difficulty and stakes are HIGH, the declared bulk role is recorded as insufficient for "
            "implementation-repair, and the route still honours the declared role"
        ) if ok else f"characterisation={characterisation.get('difficulty')} chosen={decision.get('chosen')}",
        {"characterisation": characterisation, "routing": decision},
        {"candidates": len(decision.get("candidates", [])), "model_calls": 0},
    )


@case(id="routing.escalation-chooses-stronger-candidate", group="routing",
      title="Escalation selects the lightest stronger sufficient candidate",
      task="Escalate the S4B boundary after the first attempt.",
      expectation="The new packet names a stronger worker role and the decision records the escalation rule.",
      evaluation="Compare the packet worker role with the routing decision.",
      evidence_required="Routing decision, packet manifest worker role, packet list.",
      layer="deterministic")
def routing_escalation(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="blocked")
    ctx.repo.cli("advance", "--run-root", str(box.run_root))
    before = _latest(_state(box), "routing_decisions").get("chosen", {}).get("id")
    result = ctx.repo.cli("prepare-next", "--run-root", str(box.run_root), "--escalate")
    state = _state(box)
    decision = _latest(state, "routing_decisions")
    manifest = box.manifest()
    ok = (
        result.returncode == 0
        and before == "bulk"
        and decision.get("status") == "selected"
        and decision.get("rule") == "escalation-required"
        and decision.get("chosen", {}).get("id") == "strong"
        and manifest["worker"]["role"] == "strong"
        and manifest["worker"]["attempt"] == 2
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "escalation moved the boundary from bulk to strong and the decision records the rule"
        ) if ok else f"exit={result.returncode} before={before} decision={decision.get('chosen')}",
        {"before": before, "routing": decision, "worker": manifest.get("worker", {}).get("role"),
         "attempt": manifest.get("worker", {}).get("attempt")},
        {"candidates": len(decision.get("candidates", [])), "model_calls": 0},
    )


@case(id="routing.authorization-failure-cannot-be-routed-around", group="routing",
      title="An authorization failure stops routing instead of being worked around",
      task="Produce a blocked out-of-contract validation, then try to escalate past it.",
      expectation="The escalation is refused with an authorization reason and no packet is created.",
      evaluation="Read the exit code, the packet list and the recorded routing decision.",
      evidence_required="Exit code, packet count, routing decision or pause message.",
      layer="deterministic")
def routing_authorization(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    box.write("outside-scope.txt", "not permitted by the handoff\n")
    ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    packets_before = [entry["id"] for entry in box.packets()]
    runtime = ctx.repo.module("ariadne.py")
    state = _state(box)
    failures = state.get("failures", [])
    last_class = str(failures[-1].get("class", "")) if failures else ""
    route = runtime.ROUTING.route(
        state, stage="S4B",
        characterisation=_latest(state, "characterisations")
        or runtime.ROUTING.characterize(state, project=Path(state["project"]), stage="S4B",
                                        task_id=packets_before[-1], transport=runtime.TRANSPORT),
        task_id=packets_before[-1], declared_role="bulk", escalate=True,
    )
    packets_after = [entry["id"] for entry in box.packets()]
    ok = (
        last_class == "AUTHORIZATION_FAILURE"
        and route.get("status") == "blocked"
        and route.get("rule") == "policy-excluded"
        and "authorization refusal" in str(route.get("reason", ""))
        and packets_after == packets_before
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "the out-of-contract validation is classified as an authorization failure and the router "
            "refuses to continue around it"
        ) if ok else f"class={last_class} route={route.get('status')}/{route.get('rule')} packets={len(packets_after)}",
        {"failure_class": last_class, "routing": route, "packets_before": packets_before,
         "packets_after": packets_after},
        {"packets_created": len(packets_after) - len(packets_before), "model_calls": 0},
    )


@case(id="routing.human-gate-cannot-be-routed-around", group="routing",
      title="A missing human gate is never routed around",
      task="Ask for the S4A boundary before G1 is recorded, with an explicit stage argument.",
      expectation="The boundary is refused and no packet, route or approval is invented.",
      evaluation="Compare the packet list, routing decisions and approvals before and after.",
      evidence_required="Exit code, packet list, routing decision count, approval count.",
      layer="deterministic")
def routing_human_gate(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    before = _state(box)
    result = ctx.repo.cli("prepare-next", "--run-root", str(box.run_root), "--stage", "S4A")
    after = _state(box)
    ok = (
        result.returncode in (1, 2)
        and len(after.get("packets", [])) == len(before.get("packets", []))
        and len(after.get("routing_decisions", []) or []) == len(before.get("routing_decisions", []) or [])
        and len(after.get("approvals", []) or []) == len(before.get("approvals", []) or [])
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "the unapproved boundary paused before any route, packet or approval was created"
        ) if ok else f"exit={result.returncode} packets={len(after.get('packets', []))}",
        {"exit_code": result.returncode, "tail": result.tail(3),
         "packets": len(after.get("packets", [])),
         "routing_decisions": len(after.get("routing_decisions", []) or []),
         "approvals": len(after.get("approvals", []) or [])},
        {"packets_created": 0, "model_calls": 0},
    )


@case(id="routing.requested-vs-reported-identity-recorded", group="routing",
      title="A worker runtime claim is recorded as reported identity, never as observed",
      task="Deliver an implementation return whose provider and model differ from the request.",
      expectation="The mismatch is recorded and observed identity stays UNKNOWN.",
      evaluation="Read return-handoff.json execution block and the engine events.",
      evidence_required="Machine return record, engine events, execution record.",
      layer="deterministic")
def routing_identity_recorded(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    ctx.repo.cli("preflight", "--run-root", str(box.run_root), "--model", "provider default - unverified",
                 "--availability", "available", "--quota", "sufficient")
    ctx.repo.cli("prepare-next", "--run-root", str(box.run_root))
    F.deliver_return(box, ctx.fixtures, status="complete")
    target = Path(box.manifest().get("return_target", ""))
    ctx.repo.cli("ingest-return", "--run-root", str(box.run_root), "--input", str(target))
    record_path = box.current_packet() / "evidence" / "return-handoff.json"
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else {}
    execution = (record.get("execution") or {})
    state = _state(box)
    stored = _latest(state, "executions")
    observed_events = [item for item in _events(box) if item.get("type") == "execution_observed"]
    ok = (
        record
        and execution.get("reported", {}).get("provider")
        and execution.get("observed", {}).get("provider") == "UNKNOWN"
        and execution.get("observed", {}).get("model") == "UNKNOWN"
        and bool(observed_events)
        and str(execution.get("identity_note", "")) != ""
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "the return's runtime claim was recorded as reported identity, observed identity stayed UNKNOWN "
            "and the mismatch was recorded explicitly"
        ) if ok else f"execution block={execution}",
        {"execution": execution, "observed_events": len(observed_events),
         "stored_observed": stored.get("observed")},
        {"mismatches_recorded": 1 if execution.get("mismatch") else 0, "model_calls": 0},
    )


@case(id="routing.pinned-identity-mismatch-refused", group="routing",
      title="A pinned model identity refuses a mismatched execution",
      task="Declare a concrete model, then deliver a return that reports a different one.",
      expectation="The return is refused with an identity reason and no state advances.",
      evaluation="Read the exit code and the refusal message.",
      evidence_required="Exit code, refusal text, state before/after.",
      layer="deterministic")
def routing_pinned_identity(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    ctx.repo.cli("preflight", "--run-root", str(box.run_root), "--model", "gemini-3-pro",
                 "--availability", "available", "--quota", "sufficient")
    ctx.repo.cli("prepare-next", "--run-root", str(box.run_root))
    F.deliver_return(box, ctx.fixtures, status="complete")
    target = Path(box.manifest().get("return_target", ""))
    before = box.state()
    result = ctx.repo.cli("ingest-return", "--run-root", str(box.run_root), "--input", str(target))
    after = box.state()
    ok = (
        result.returncode == 1
        and "does not match the pinned provider/model" in result.combined
        and not (box.current_packet() / "evidence" / "return-handoff.md").is_file()
        and len(after.get("failures", []) or []) == len(before.get("failures", []) or []) + 1
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "the pinned model identity refused the mismatched return and the refusal is recorded as a failure"
        ) if ok else f"exit={result.returncode} tail={result.tail(3)}",
        {"exit_code": result.returncode, "tail": result.tail(3),
         "failures_before": len(before.get("failures", []) or []),
         "failures_after": len(after.get("failures", []) or [])},
        {"return_recorded": 0, "model_calls": 0},
    )


# ========================================================= execution-identity

@case(id="execution-identity.bound-to-boundary", group="execution-identity",
      title="The prepared boundary owns an engine-created execution identity",
      task="Prepare S4B and inspect the execution record and operator status command.",
      expectation="The identity is engine-generated, bound to the packet and revision, and observed identity is UNKNOWN.",
      evaluation="Read the run state execution record and the execution-status output.",
      evidence_required="Execution record, status output, structural validation.",
      layer="deterministic")
def identity_bound(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    state = _state(box)
    runtime = ctx.repo.module("ariadne.py")
    record = _latest(state, "executions")
    worker = state.get("worker", {})
    manifest = box.manifest()
    problems = runtime.CONTRACTS.execution_problems(record)
    status = ctx.repo.cli("execution-status", "--run-root", str(box.run_root), "--json")
    ok = (
        not problems
        and record.get("role") == "implementer"
        and str(record.get("task_id")) == str(manifest.get("packet_id"))
        and record.get("provenance", {}).get("created_by") == "engine"
        and record.get("observed", {}).get("provider") == "UNKNOWN"
        and record.get("state") in ("CREATED", "STARTED")
        and worker.get("execution_id") == record.get("execution_id")
        and status.returncode == 0
        and '"executions"' in status.combined
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            f"execution {record.get('execution_id')} is engine-bound to packet {record.get('task_id')} "
            "and observed identity is UNKNOWN"
        ) if ok else f"problems={problems} record={record.get('state')}",
        {"execution": record, "problems": problems, "worker_execution": worker.get("execution_id"),
         "status_exit": status.returncode},
        {"executions": len(state.get("executions", []) or []), "model_calls": 0},
    )


@case(id="execution-identity.forged-and-replayed-refused", group="execution-identity",
      title="A forged, foreign or replayed execution identity is refused",
      task="Submit results naming an unknown execution, another task's execution and a finished execution.",
      expectation="Each attempt is refused and only the engine-created identity is accepted.",
      evaluation="Read the refusals, the engine verification and the recorded execution state.",
      evidence_required="Exit codes, refusal messages, engine verification results.",
      layer="deterministic")
def identity_forged(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    runtime = ctx.repo.module("ariadne.py")
    target = Path(box.manifest().get("return_target", ""))
    F.deliver_return(box, ctx.fixtures, status="complete")
    forged = ctx.repo.cli("ingest-return", "--run-root", str(box.run_root), "--input", str(target),
                          "--execution", "exe_20260101T000000Z_deadbeef")
    state = _state(box)
    implementer = _latest(state, "executions")
    implementer_id = str(implementer.get("execution_id"))
    accepted = ctx.repo.cli("ingest-return", "--run-root", str(box.run_root), "--input", str(target))
    replay_problems = runtime.EXECUTION.verify_result(
        _state(box), implementer_id, role="implementer",
        task_id=str(box.manifest().get("packet_id")),
    )
    foreign_problems = runtime.EXECUTION.verify_result(
        _state(box), implementer_id, role="implementer", task_id="some-other-packet",
    )
    ok = (
        forged.returncode == 1
        and "was not created by this engine" in forged.combined
        and accepted.returncode == 0
        and replay_problems != []
        and any("already finished" in item for item in replay_problems)
        and foreign_problems != []
        and any("not" in item for item in foreign_problems)
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "the forged id was refused before any evidence was written; the accepted result closed the "
            "execution so a replay and a foreign-task result are both refused"
        ) if ok else f"forged={forged.returncode} accepted={accepted.returncode} replay={replay_problems}",
        {"forged_exit": forged.returncode, "forged_tail": forged.tail(2), "accepted_exit": accepted.returncode,
         "replay_problems": replay_problems, "foreign_problems": foreign_problems},
        {"forged_refusals": 1, "model_calls": 0},
    )


@case(id="execution-identity.review-binds-two-executions", group="execution-identity",
      title="A review binds the implementation and review executions separately",
      task="Reach S5, try to review as the implementing execution, then record a real review.",
      expectation="Binding the implementer as reviewer is refused; the recorded review names two distinct executions.",
      evaluation="Read the refusal, the review record and the run state executions.",
      evidence_required="Refusal message, review record, execution records.",
      layer="deterministic")
def identity_review(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    F.prepare_s5(ctx.repo, box)
    state = _state(box)
    implementer = next((item for item in state.get("executions", []) if item.get("role") == "implementer"), {})
    source = box.root / "review-source.md"
    review = ctx.fixtures["review"]()
    source.write_text(review, encoding="utf-8")
    refused = ctx.repo.cli("ingest-review", "--run-root", str(box.run_root), "--input", str(source),
                           "--reviewer-identity", F.REVIEWER_IDENTITY,
                           "--execution", str(implementer.get("execution_id")))
    accepted = F.ingest_independent_review(ctx.repo, box, source)
    record_path = box.current_packet() / "evidence" / "review-record.json"
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else {}
    ok = (
        refused.returncode == 1
        and "not a reviewer execution" in refused.combined
        and accepted.returncode == 0
        and record.get("execution_binding") == "engine"
        and record.get("reviewer_execution")
        and record.get("implementing_execution") == implementer.get("execution_id")
        and record.get("reviewer_execution") != record.get("implementing_execution")
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "binding the implementer as the reviewer was refused, and the recorded review names two "
            "distinct engine-created executions"
        ) if ok else f"refused={refused.returncode} accepted={accepted.returncode} record={record}",
        {"refusal_tail": refused.tail(2), "reviewer_execution": record.get("reviewer_execution"),
         "implementing_execution": record.get("implementing_execution")},
        {"independent_executions": 2, "model_calls": 0},
    )


@case(id="execution-identity.stale-revision-refused", group="execution-identity",
      title="An execution bound to another revision cannot deliver a result",
      task="Prepare S4B, move the project revision on, then deliver the recorded return.",
      expectation="The engine refuses the result as bound to a different revision.",
      evaluation="Read the execution revision, the current packet revision and the refusal.",
      evidence_required="Execution revision, packet revision, refusal message.",
      layer="deterministic")
def identity_stale_revision(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    runtime = ctx.repo.module("ariadne.py")
    target = Path(box.manifest().get("return_target", ""))
    F.deliver_return(box, ctx.fixtures, status="complete")
    state = _state(box)
    implementer = _latest(state, "executions")
    packet = box.current_packet()
    manifest_path = packet / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["project_baseline"] = dict(manifest.get("project_baseline") or {})
    manifest["project_baseline"]["head"] = "0" * 40
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = ctx.repo.cli("ingest-return", "--run-root", str(box.run_root), "--input", str(target),
                          "--execution", str(implementer.get("execution_id")))
    ok = (
        result.returncode == 1
        and "different revision" in result.combined
        and not (packet / "evidence" / "return-handoff.md").is_file()
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "the execution's recorded revision no longer matched the boundary, so the result was refused "
            "before any evidence was written"
        ) if ok else f"exit={result.returncode} tail={result.tail(3)}",
        {"exit_code": result.returncode, "tail": result.tail(3),
         "execution_revision": (implementer.get("revision") or {}).get("revision_hash")},
        {"stale_results_refused": 1, "model_calls": 0},
    )


# ==================================================================== recovery

@case(id="recovery.adopts-orphan-packet-with-backup", group="recovery",
      title="A recoverable orphan packet is adopted through the engine boundary",
      task="Simulate a crash between writing the S3 packet and recording its transition, then recover.",
      expectation="The orphan is reported, adopted only with an operator identity and reason, and the pre-recovery state is preserved.",
      evaluation="Inspect the report, the applied recovery record, the transition and the backup bytes.",
      evidence_required="Recovery report, recovery record, transition, backup digest.",
      layer="deterministic")
def recovery_adopt(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    state = _state(box)
    orphan_entry = state["packets"].pop()
    _write_state(box, state)
    before_bytes = (box.run_root / "ariadne-run.json").read_bytes()
    inspect = ctx.repo.cli("recover", "--run-root", str(box.run_root), "--json")
    applied = ctx.repo.cli("recover", "--run-root", str(box.run_root), "--apply", "adopt-packet",
                           "--target", orphan_entry["id"], "--identity", F.OPERATOR_IDENTITY,
                           "--reason", "the packet was written before the crash and its parent is the tip")
    after = _state(box)
    record = _latest(after, "recoveries")
    backup = Path(str(record.get("backup", "")))
    transitions = after.get("transitions", [])
    ok = (
        inspect.returncode == 2
        and "orphan-packet" in inspect.combined
        and applied.returncode == 0
        and record.get("outcome") == "applied"
        and record.get("action") == "adopt-packet"
        and len(after.get("packets", [])) == 2
        and after["packets"][-1]["id"] == orphan_entry["id"]
        and any(item.get("kind") == "stage" and item.get("operation") == "recovery:adopt-packet"
                for item in transitions)
        and backup.is_file()
        and backup.read_bytes() == before_bytes
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "the orphan packet was adopted through the authoritative transition boundary and the "
            "pre-recovery state is preserved byte-identically"
        ) if ok else f"inspect={inspect.returncode} applied={applied.returncode} record={record.get('outcome')}",
        {"inspect_exit": inspect.returncode, "applied_exit": applied.returncode,
         "recovery": record, "packets": [entry["id"] for entry in after.get("packets", [])],
         "backup_preserved": bool(backup.is_file() and backup.read_bytes() == before_bytes)},
        {"recoveries_applied": 1, "model_calls": 0},
    )


@case(id="recovery.refuses-ambiguous-orphan", group="recovery",
      title="An ambiguous orphan packet is refused rather than adopted",
      task="Leave a packet directory whose recorded parent is not the current tip and try to adopt it.",
      expectation="Recovery refuses with a reason and changes nothing.",
      evaluation="Read the refusal, the packet list and the recovery records.",
      evidence_required="Refusal message, packet list, recovery records.",
      layer="deterministic")
def recovery_refuse(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    orphan = box.run_root / "bench-S3-C9"
    (orphan / "evidence").mkdir(parents=True, exist_ok=True)
    (orphan / "manifest.json").write_text(json.dumps({
        "packet_id": "bench-S3-C9", "stage": "S3", "parent_id": "not-the-tip",
    }), encoding="utf-8")
    before = _state(box)
    inspect = ctx.repo.cli("recover", "--run-root", str(box.run_root), "--json")
    applied = ctx.repo.cli("recover", "--run-root", str(box.run_root), "--apply", "adopt-packet",
                           "--target", "bench-S3-C9", "--identity", F.OPERATOR_IDENTITY,
                           "--reason", "attempt to adopt an unrelated orphan")
    after = _state(box)
    ok = (
        inspect.returncode == 2
        and '"safe": false' in inspect.combined
        and applied.returncode == 1
        and "refused" in applied.combined
        and "not the current tip" in applied.combined
        and after.get("packets") == before.get("packets")
        and not (after.get("recoveries") or [])
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "an orphan whose parent is not the tip was refused, not adopted, and nothing changed"
        ) if ok else f"inspect={inspect.returncode} applied={applied.returncode}",
        {"inspect_exit": inspect.returncode, "applied_exit": applied.returncode,
         "applied_tail": applied.tail(2), "packets": len(after.get("packets", []))},
        {"orphans_adopted": 0, "model_calls": 0},
    )


@case(id="recovery.abandons-interrupted-execution", group="recovery",
      title="An open execution that cannot finish is recorded as interrupted",
      task="Prepare an S4B attempt, escalate past it, then recover the stranded execution.",
      expectation="The stranded execution is reported and abandoned with class INTERRUPTED, not as success.",
      evaluation="Read the findings, the recovery record, the execution state and the failure class.",
      evidence_required="Recovery report, recovery record, execution state, failure record.",
      layer="deterministic")
def recovery_abandon(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    stranded = _latest(_state(box), "executions")
    # The attempt never returned a result: the operator saved the session transcript
    # (a declared parent-evidence kind) and escalated past the dead attempt.
    transcript = box.current_packet() / "evidence" / "transcript.md"
    transcript.write_text(
        "# Saved session transcript\n\nThe worker session ended before a return handoff.\n",
        encoding="utf-8",
    )
    ctx.repo.cli("prepare-next", "--run-root", str(box.run_root), "--escalate")
    inspect = ctx.repo.cli("recover", "--run-root", str(box.run_root), "--json")
    applied = ctx.repo.cli("recover", "--run-root", str(box.run_root), "--apply", "abandon-execution",
                           "--target", str(stranded.get("execution_id")), "--identity", F.OPERATOR_IDENTITY,
                           "--reason", "the boundary moved on and this attempt can never produce a result")
    state = _state(box)
    record = _latest(state, "recoveries")
    refreshed = next((item for item in state.get("executions", [])
                      if item.get("execution_id") == stranded.get("execution_id")), {})
    failure = _latest(state, "failures")
    ok = (
        inspect.returncode == 2
        and "interrupted-execution" in inspect.combined
        and applied.returncode == 0
        and record.get("outcome") == "applied"
        and refreshed.get("state") == "FAILED"
        and failure.get("class") == "INTERRUPTED"
        and failure.get("execution") == stranded.get("execution_id")
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "the stranded execution was abandoned with class INTERRUPTED and no result was fabricated"
        ) if ok else f"inspect={inspect.returncode} applied={applied.returncode} state={refreshed.get('state')}",
        {"inspect_exit": inspect.returncode, "applied_exit": applied.returncode,
         "execution_state": refreshed.get("state"), "failure": failure},
        {"recoveries_applied": 1, "results_fabricated": 0, "model_calls": 0},
    )


@case(id="recovery.quarantines-interrupted-write", group="recovery",
      title="A leftover temporary state file is quarantined, not deleted silently",
      task="Leave an interrupted state write beside a live run and recover it.",
      expectation="The file is reported, moved to quarantine with its digest recorded, and the live state is untouched.",
      evaluation="Compare the live state bytes, the quarantine location and the recorded evidence.",
      evidence_required="Recovery record, quarantine path, state digest before and after.",
      layer="deterministic")
def recovery_interrupted_write(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    temp = box.run_root / ".ariadne-run.json.aborted.tmp"
    temp.write_text("{\"partial\": true}\n", encoding="utf-8")
    state_path = box.run_root / "ariadne-run.json"
    digest_before = hashlib.sha256(state_path.read_bytes()).hexdigest()
    inspect = ctx.repo.cli("recover", "--run-root", str(box.run_root), "--json")
    applied = ctx.repo.cli("recover", "--run-root", str(box.run_root), "--apply", "clear-interrupted-write",
                           "--target", str(temp), "--identity", F.OPERATOR_IDENTITY,
                           "--reason", "the live state is intact and the temporary file is not state")
    state = _state(box)
    record = _latest(state, "recoveries")
    moved = Path(str(record.get("after", "")))
    backup = Path(str(record.get("backup", "")))
    preserved = (
        backup.is_file()
        and hashlib.sha256(backup.read_bytes()).hexdigest() == digest_before
    )
    ok = (
        inspect.returncode == 2
        and "interrupted-write" in inspect.combined
        and applied.returncode == 0
        and not temp.exists()
        and moved.is_file()
        and moved.read_text(encoding="utf-8") == "{\"partial\": true}\n"
        and record.get("evidence")
        and [entry["id"] for entry in state.get("packets", [])] == ["bench-S1"]
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "the interrupted write was moved to quarantine with its digest recorded and the recorded "
            "packet list is unchanged"
        ) if ok else f"inspect={inspect.returncode} applied={applied.returncode} moved={moved}",
        {"inspect_exit": inspect.returncode, "applied_exit": applied.returncode,
         "quarantine": str(moved), "quarantined_bytes": moved.read_text(encoding="utf-8") if moved.is_file() else "",
         "recorded_evidence": record.get("evidence")},
        {"files_deleted": 0, "model_calls": 0},
    )


# ====================================================== evidence-continuation

@case(id="evidence-continuation.s4b-blocked-without-planning-evidence", group="evidence-continuation",
      title="S4B is refused when the S4A planning work has no recorded evidence",
      task="Reach S4A with a complete handoff but without recording the implementation-planning skill.",
      expectation="The boundary is refused with the exact evidence requirement and no packet is created.",
      evaluation="Read the exit code, the pause message and the packet list.",
      evidence_required="Exit code, refusal message, packet list, requirement states.",
      layer="deterministic")
def evidence_s4b_missing(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    F.lock_g1(box, ctx.repo)
    F.approve_s3_and_reach_s4a(ctx.repo, box)
    F.write_handoff(box, ctx.fixtures)
    box.write("AGENTS.md", F.agents_md("S4", "G1", "prompts/build-kickoff.md"))
    ctx.repo.cli("record-result", "--run-root", str(box.run_root), "--status", "complete",
                 "--provider", "benchmark-fixture", "--model", "none",
                 "--summary", "Implementation handoff complete",
                 "--file", "HANDOFF.md", "--file", "AGENTS.md")
    ctx.repo.cli("preflight", "--run-root", str(box.run_root), "--availability", "available",
                 "--quota", "sufficient")
    before = [entry["id"] for entry in box.packets()]
    result = ctx.repo.cli("prepare-next", "--run-root", str(box.run_root))
    after = [entry["id"] for entry in box.packets()]
    state = _state(box)
    runtime = ctx.repo.module("ariadne.py")
    requirements = runtime.POLICY.evidence_requirements(state, "S4B", project=Path(state["project"]))
    ok = (
        result.returncode == 2
        and "creative-intelligence evidence for S4A" in result.combined
        and "unresolved" in result.combined
        and after == before
        and any(item.get("state") == "unresolved" and item.get("required") for item in requirements)
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "the S4B boundary was refused because the S4A implementation planning had no recorded evidence"
        ) if ok else f"exit={result.returncode} packets={len(after)} tail={result.tail(2)}",
        {"exit_code": result.returncode, "tail": result.tail(3), "requirements": requirements},
        {"packets_created": 0, "model_calls": 0},
    )


@case(id="evidence-continuation.s5-blocked-without-qa-evidence", group="evidence-continuation",
      title="S5 is refused when the S4B QA work has no recorded evidence",
      task="Validate a complete implementation return without recording the QA skill or the implementation trace.",
      expectation="The review boundary is refused with the evidence requirement named.",
      evaluation="Read the exit code, the pause message and the requirement states.",
      evidence_required="Exit code, refusal message, requirement states.",
      layer="deterministic")
def evidence_s5_missing(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    before = [entry["id"] for entry in box.packets()]
    result = ctx.repo.cli("prepare-next", "--run-root", str(box.run_root),
                          "--target", "http://127.0.0.1:3000", "--lenses", "creative-director (light)")
    after = [entry["id"] for entry in box.packets()]
    state = _state(box)
    runtime = ctx.repo.module("ariadne.py")
    requirements = runtime.POLICY.evidence_requirements(state, "S5", project=Path(state["project"]))
    sources = {item.get("source") for item in requirements if item.get("state") != "satisfied"}
    ok = (
        result.returncode == 2
        and after == before
        and "creative-intelligence" in sources
        and "creative-operations" in sources
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "the review boundary was refused because the S4B skill evidence and the implementation trace "
            "were not recorded"
        ) if ok else f"exit={result.returncode} unmet={sorted(sources)} tail={result.tail(2)}",
        {"exit_code": result.returncode, "tail": result.tail(3), "requirements": requirements},
        {"packets_created": 0, "model_calls": 0},
    )


@case(id="evidence-continuation.stale-evidence-refused", group="evidence-continuation",
      title="Evidence whose artifact changed after it was recorded is refused as stale",
      task="Record the S4A planning evidence, then change the artifact it names.",
      expectation="The boundary is refused as stale instead of accepting the recorded claim.",
      evaluation="Compare the artifact digest with the recorded evidence digest.",
      evidence_required="Exit code, stale requirement detail, artifact digests.",
      layer="deterministic")
def evidence_stale(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    F.complete_s1(ctx.repo, box, ctx.fixtures)
    F.to_s3(ctx.repo, box)
    F.lock_g1(box, ctx.repo)
    F.approve_s3_and_reach_s4a(ctx.repo, box)
    F.write_handoff(box, ctx.fixtures)
    box.write("AGENTS.md", F.agents_md("S4", "G1", "prompts/build-kickoff.md"))
    ctx.repo.cli("record-result", "--run-root", str(box.run_root), "--status", "complete",
                 "--provider", "benchmark-fixture", "--model", "none",
                 "--summary", "Implementation handoff complete",
                 "--file", "HANDOFF.md", "--file", "AGENTS.md")
    F.record_skill_evidence(ctx.repo, box, skill="implementation-planning", output_relative="HANDOFF.md",
                            result="The handoff became the bounded build context.",
                            events_name="planning-events.json")
    recorded = box.sha256("HANDOFF.md")
    box.append("HANDOFF.md", "\n**Note:** edited after the planning evidence was recorded.\n")
    edited = box.sha256("HANDOFF.md")
    ctx.repo.cli("preflight", "--run-root", str(box.run_root), "--availability", "available",
                 "--quota", "sufficient")
    before = [entry["id"] for entry in box.packets()]
    result = ctx.repo.cli("prepare-next", "--run-root", str(box.run_root))
    after = [entry["id"] for entry in box.packets()]
    state = _state(box)
    runtime = ctx.repo.module("ariadne.py")
    requirements = runtime.POLICY.evidence_requirements(state, "S4B", project=Path(state["project"]))
    ok = (
        result.returncode == 2
        and after == before
        and any(item.get("state") == "stale" for item in requirements)
        and recorded != edited
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "the recorded planning evidence no longer matched its artifact, so the boundary was refused "
            "as stale"
        ) if ok else f"exit={result.returncode} states={[item.get('state') for item in requirements]}",
        {"exit_code": result.returncode, "tail": result.tail(3),
         "recorded_artifact_sha256": recorded, "current_artifact_sha256": edited,
         "requirements": requirements},
        {"stale_refusals": 1, "model_calls": 0},
    )


@case(id="evidence-continuation.satisfied-evidence-proceeds", group="evidence-continuation",
      title="Satisfied evidence lets the same boundaries proceed",
      task="Record the S4A planning evidence, the S4B QA evidence and the implementation trace, then continue.",
      expectation="Every requirement is satisfied and both boundaries are prepared.",
      evaluation="Read the requirement states and the prepared stages.",
      evidence_required="Requirement states, packet stages.",
      layer="deterministic")
def evidence_satisfied(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    s4b = F.clear_preflight_and_reach_s4b(ctx.repo, box)
    F.deliver_return(box, ctx.fixtures, status="complete")
    ctx.repo.cli("validate-worker", "--run-root", str(box.run_root))
    s5 = F.prepare_s5(ctx.repo, box)
    state = _state(box)
    runtime = ctx.repo.module("ariadne.py")
    project = Path(state["project"])
    stages = [entry["stage"] for entry in state.get("packets", [])]
    s4b_requirements = runtime.POLICY.evidence_requirements(state, "S4B", project=project)
    s5_requirements = runtime.POLICY.evidence_requirements(state, "S5", project=project)
    unmet = [item for item in s4b_requirements + s5_requirements
             if item.get("required") and item.get("state") != "satisfied"]
    ok = (
        s4b.returncode == 0
        and s5.returncode == 0
        and stages[-2:] == ["S4B", "S5"]
        and not unmet
    )
    return Outcome(
        "pass" if ok else "fail",
        (
            "every declared evidence requirement is satisfied and both boundaries were prepared"
        ) if ok else f"s4b={s4b.returncode} s5={s5.returncode} unmet={unmet}",
        {"s4b_exit": s4b.returncode, "s5_exit": s5.returncode, "stages": stages,
         "unmet": unmet, "requirements": s5_requirements},
        {"requirements_satisfied": len(s4b_requirements) + len(s5_requirements), "model_calls": 0},
    )
