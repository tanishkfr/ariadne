"""AR-204 measurement cases: real packet economics and local performance.

These cases are ``observed``: they record measurements from real assembled packets
and real engine calls rather than asserting a pass/fail. They exist so the AR-204
baseline document quotes numbers produced by the repository's own harness under
the same fixed fixture as every other case, and so the numbers can be re-derived
by re-running the case.

No provider is called, no network is used, and nothing is estimated: every figure
is either a byte count of a real artifact, a measured duration, or a count taken
from a real engine record.
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path

from .cases import Ctx, Outcome, case
from . import fixtures as F


def _timed(callable_, *, repeats: int = 25, warmup: int = 5) -> dict:
    """Warm up, repeat, and report median/p90/min/max in milliseconds."""
    for _ in range(warmup):
        callable_()
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        callable_()
        samples.append((time.perf_counter() - started) * 1000.0)
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1)))))
    return {
        "repeats": repeats,
        "warmup": warmup,
        "median_ms": round(statistics.median(samples), 4),
        "p90_ms": round(ordered[index], 4),
        "min_ms": round(min(samples), 4),
        "max_ms": round(max(samples), 4),
    }


def _packet_render(module, packet_dir: Path) -> dict:
    text = (Path(packet_dir) / "packet.txt").read_text(encoding="utf-8")
    mapping = module.HARNESS.packet_map(text)
    compact = module.PROMPTING.compact_packet_text(text, profile="compact_v2")
    legacy = module.PROMPTING.compact_packet_text(text, profile="legacy")
    return {
        "bytes": mapping["measured_size"]["total_bytes"],
        "sections": len(mapping["sections"]),
        "section_rows": [
            {
                "label": str(item["label"])[:60],
                "bucket": item["bucket"],
                "bytes": item["bytes"],
                "stability": item["stability"],
                "stability_basis": item["stability_basis"],
                "per_request": item["per_request_volatile"],
            }
            for item in mapping["sections"]
        ],
        "stable_prefix_bytes": mapping["stable_prefix"]["stable_prefix_bytes"],
        "volatile_bytes": mapping["stable_prefix"]["volatile_bytes"],
        "stable_ratio": round(
            mapping["stable_prefix"]["stable_prefix_bytes"]
            / max(1, mapping["measured_size"]["total_bytes"]), 4),
        "buckets": {name: entry["bytes"] for name, entry in mapping["source_buckets"]["buckets"].items()},
        "volatile_kinds": sorted({
            kind for section in mapping["sections"] for kind in section["volatile"]
        }),
        "redactions": mapping["measured_size"]["redactions"],
        "compact_profile_removed_bytes": compact["removed_bytes"],
        "compact_profile_removed_share": round(
            compact["removed_bytes"] / max(1, legacy["bytes_after"]), 4),
        "compact_sources_untouched": not compact["sources_touched"],
    }


@case(
    id="harness-metrics.packet-economics",
    group="harness-metrics",
    title="Rendered packet economics for every prepared stage",
    task="Assemble real S1, S3, S4A and S4B packets and measure their rendered structure.",
    expectation="Measurement-only: bytes, buckets, stable/volatile split and the compact-profile delta.",
    evaluation="Render each packet with the harness and the prompt profiles and record the figures.",
    evidence_required="Per-stage measurements plus the tool-schema and prompt-audit totals.",
    layer="deterministic",
)
def harness_packet_economics(ctx: Ctx) -> Outcome:
    module = ctx.repo.module("ariadne.py")
    box = ctx.sandbox()
    F.reach_s4a_with_handoff(ctx.repo, box, ctx.fixtures)
    F.clear_preflight_and_reach_s4b(ctx.repo, box)
    packets = box.packets()
    stages = [_packet_render(module, Path(entry["path"])) for entry in packets]
    by_stage = {str(entry["stage"]): stages[index] for index, entry in enumerate(packets)}

    sizes = module.TOOLING.pack_sizes(root=ctx.repo.root)
    prompt_audit = module.PROMPTING.audit_prompt_directory(
        ctx.repo.root, ["prompts/build-kickoff.md", "prompts/design-direction.md", "prompts/project-start.md"],
    )
    total_bytes = sum(stage["bytes"] for stage in stages)
    stable_bytes = sum(stage["stable_prefix_bytes"] for stage in stages)
    volatile_bytes = sum(stage["volatile_bytes"] for stage in stages)
    removed = sum(stage["compact_profile_removed_bytes"] for stage in stages)
    return Outcome(
        "observed",
        f"{len(stages)} packets, {total_bytes} bytes; stable {stable_bytes}, volatile {volatile_bytes}; "
        f"compact profile would remove {removed} bytes",
        {
            "stages": by_stage,
            "totals": {
                "packets": len(stages),
                "bytes": total_bytes,
                "stable_prefix_bytes": stable_bytes,
                "volatile_bytes": volatile_bytes,
                "stable_ratio": round(stable_bytes / max(1, total_bytes), 4),
                "compact_profile_removed_bytes": removed,
                "compact_profile_removed_share": round(removed / max(1, total_bytes), 4),
            },
            "tool_schemas": {
                "core_bytes": sizes["core_bytes"],
                "deferrable_bytes": sizes["deferrable_bytes"],
                "deferrable_share": round(
                    sizes["deferrable_bytes"] / max(1, sizes["core_bytes"] + sizes["deferrable_bytes"]), 4),
                "packs": {name: entry["bytes"] for name, entry in sizes["packs"].items()},
            },
            "prompt_audit": {
                "files": len(prompt_audit["files"]),
                "bytes": prompt_audit["total_bytes"],
                "keep_bytes": prompt_audit["keep_bytes"],
                "delete_bytes": prompt_audit["delete_bytes"],
                "rewrite_bytes": prompt_audit["rewrite_bytes"],
                "move_bytes": prompt_audit["move_bytes"],
            },
            "thresholds": {
                "externalize_at_bytes": module.ARTIFACTS.DEFAULT_EXTERNALIZE_AT_BYTES,
                "excerpt_bytes": module.ARTIFACTS.DEFAULT_EXCERPT_BYTES,
                "tail_bytes": module.ARTIFACTS.DEFAULT_TAIL_BYTES,
            },
            "note": (
                "bytes are measured from real packet artifacts; the compact-profile delta is structural "
                "and no model-quality parity is implied"
            ),
        },
        {"packets": len(stages), "packet_bytes": total_bytes, "stable_prefix_bytes": stable_bytes,
         "volatile_bytes": volatile_bytes, "compact_profile_removed_bytes": removed, "model_calls": 0},
    )


@case(
    id="harness-metrics.local-performance",
    group="harness-metrics",
    title="Local performance of the AR-204 operations",
    task="Time the new engine operations with warm-up and repeats on a real packet and a real history.",
    expectation="Measurement-only: median and p90 for rendering, serialization, compaction and accounting.",
    evaluation="Warm up, repeat and record the median and p90 wall time per operation.",
    evidence_required="Per-operation timing statistics and the memo hit rate.",
    layer="deterministic",
)
def harness_local_performance(ctx: Ctx) -> Outcome:
    module = ctx.repo.module("ariadne.py")
    box = ctx.sandbox()
    F.start_s1(ctx.repo, box)
    packet_text = (box.current_packet() / "packet.txt").read_text(encoding="utf-8")

    source = box.write("source.py", "print('x')\n" * 400)

    def hash_source() -> None:
        module.SERIALIZATION.digest_bytes(source.read_bytes())

    memo = module.SERIALIZATION.Memo("perf-source")
    dependency = {"size": source.stat().st_size, "mtime_ns": source.stat().st_mtime_ns}

    def memoised_hash() -> None:
        hit = memo.get(source, dependency)
        if hit is None:
            memo.put(source, dependency, module.SERIALIZATION.digest_text(source.read_text(encoding="utf-8")),
                     kind="digest")

    entries = [
        module.HISTORY.entry(
            "tool_output" if index % 3 == 0 else ("conversation" if index % 3 == 1 else "decision"),
            f"entry {index} " + ("noise " * 40),
            turn=index,
        )
        for index in range(60)
    ]
    plan = module.ORCHESTRATION.path_plan(stakes="MEDIUM", required_capabilities=["edit"])
    state = {
        "schema_version": 1, "run_id": "perf", "project": str(box.project), "run_root": str(box.run_root),
        "packets": [{"id": "perf-S1", "stage": "S1", "path": str(box.current_packet())}],
        "approvals": [],
    }
    timings = {
        "packet_map": _timed(lambda: module.HARNESS.packet_map(packet_text)),
        "render_request": _timed(lambda: module.HARNESS.packet_render(packet_text)),
        "compact_packet_text": _timed(
            lambda: module.PROMPTING.compact_packet_text(packet_text, profile="compact_v2")),
        "stable_prefix": _timed(lambda: module.SERIALIZATION.stable_prefix([
            module.SERIALIZATION.segment("a", packet_text[:4000]),
            module.SERIALIZATION.segment("b", packet_text[4000:8000], stability="volatile"),
        ])),
        "canonical_json": _timed(lambda: module.SERIALIZATION.canonical_json({"z": list(range(500)), "a": "x"})),
        "raw_source_hash": _timed(hash_source, repeats=25, warmup=5),
        "memoised_source_hash": _timed(memoised_hash, repeats=25, warmup=5),
        "pack_sizes": _timed(lambda: module.TOOLING.pack_sizes(root=ctx.repo.root), repeats=15, warmup=3),
        "history_economics": _timed(lambda: module.HISTORY.history_economics(entries), repeats=25, warmup=5),
        "history_compact": _timed(lambda: module.HISTORY.compact(box.root / "history-work", entries),
                                  repeats=15, warmup=3),
        "task_tree": _timed(lambda: module.ECONOMICS.task_tree(state, "perf-S1"), repeats=25, warmup=5),
        "path_plan": _timed(lambda: module.ORCHESTRATION.path_plan(stakes="MEDIUM"), repeats=25, warmup=5),
    }
    memo_stats = memo.stats()
    # A cold call: the harness memo is cleared so the reported cold figure is the
    # genuine first-render cost rather than a warm repeat.
    module.HARNESS._ANALYSIS_MEMO.invalidate()
    cold_started = time.perf_counter()
    module.HARNESS.packet_map(packet_text)
    cold_packet_map_ms = round((time.perf_counter() - cold_started) * 1000.0, 4)
    module.HARNESS._ANALYSIS_MEMO.invalidate()
    cold_started = time.perf_counter()
    module.HARNESS.packet_render(packet_text)
    cold_render_ms = round((time.perf_counter() - cold_started) * 1000.0, 4)
    slowest = max(timings.items(), key=lambda item: item[1]["median_ms"])
    return Outcome(
        "observed",
        f"slowest warm median {slowest[0]} at {slowest[1]['median_ms']} ms; cold packet_map "
        f"{cold_packet_map_ms} ms, cold render {cold_render_ms} ms; memo hits "
        f"{memo_stats['hits']}/{memo_stats['hits'] + memo_stats['misses']}",
        {
            "timings_ms": timings,
            "cold_ms": {"packet_map": cold_packet_map_ms, "packet_render": cold_render_ms},
            "memo": memo_stats,
            "notes": [
                "each operation is warmed up and repeated; medians are reported, not single samples",
                "cold figures clear the section-analysis memo first, so they are genuine first-render costs",
                "timings are from this host and this packet; they are comparable with each other, not with "
                "another machine",
            ],
        },
        {"model_calls": 0, "operations": len(timings), "slowest_median_ms": slowest[1]["median_ms"],
         "cold_packet_map_ms": cold_packet_map_ms, "memo_hits": memo_stats["hits"]},
    )
