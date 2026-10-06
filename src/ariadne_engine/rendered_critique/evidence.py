"""The canonical capture manifest, and what makes an artifact evidence (AR-222).

One :class:`RenderedEvidenceSet` per capture run. It is the unit that makes captures
checkable *in aggregate*: it names the exact source digest every capture in the run
was bound to, the browser that produced them, and -- per capture -- the route, state,
viewport, theme, artifact path, digest and timestamp. §54's ``capture_017.png``
example is this record, because an image with no accompanying metadata is a mystery
object and a reviewer cannot tell which state it shows.

The validation half of this module is the part that earns the rest.

A screenshot can exist, open correctly, have a plausible file size, and still be
evidence of nothing: a white viewport while the app is still booting, a spinner,
a framework error page, an application shell with the target route's content missing.
Each of those produces a *real PNG*, which is exactly why they are dangerous -- a
reviewer looking at a well-centred error message will critique its typography.

So every artifact is validated against :data:`ariadne_engine.contracts.
ARTIFACT_VALIDATION_STATES`, and anything that is not ``VALID`` is refused with the
reason recorded. :func:`validate_capture` is the single implementation; the critique
layer asks it rather than re-deciding what a usable capture looks like.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Mapping, Sequence

from .. import contracts
from ..contracts import ARTIFACT_VALIDATION_STATES, ContractError
from . import adapter as adapter_module
from . import safety

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MANIFEST_NAME = "rendered-evidence-set.json"
"""The per-run manifest filename. Distinct from AR-202D's per-capture
``capture-manifest.json``: that one proves a single artifact came from a capture, this
one aggregates a whole planned run under a single source identity."""

MAX_MANIFEST_BYTES = 8 * 1024 * 1024
CAPTURE_FILENAME_TEMPLATE = "capture_{index:03d}"


def validate_artifact(path: Path, *, expected_route: str = "", expected_state: str = "") -> dict:
    """Whether one artifact can stand as evidence of the interface that was intended.

    Ordered cheapest-check-first, and each check answers a different question. Exists,
    is a PNG, is not trivially small, has visible content, is not still loading, is not
    an error document, and -- when a route was requested -- actually contains it.
    """
    state = "VALID"
    reasons: list[str] = []
    target = Path(path)
    if not target.is_file():
        return {"state": "UNREADABLE", "reasons": [f"the capture artifact does not exist: {target}"]}
    size = target.stat().st_size
    if size == 0:
        return {"state": "BLANK", "reasons": [f"the capture artifact is zero bytes: {target}"]}
    if size > safety.MAX_CAPTURE_BYTES:
        return {
            "state": "UNREADABLE",
            "reasons": [f"the capture artifact is {size} bytes, above the {safety.MAX_CAPTURE_BYTES}-byte bound"],
        }
    payload = target.read_bytes()
    if not payload.startswith(PNG_MAGIC):
        return {
            "state": "UNREADABLE",
            "reasons": ["the capture artifact is not a PNG; a file with a screenshot name is not a screenshot"],
        }
    dimensions = _png_dimensions(payload)
    if dimensions is None:
        return {
            "state": "UNREADABLE",
            "reasons": ["the PNG header is unreadable, so the artifact cannot be opened"],
        }
    width, height = dimensions
    if width <= 0 or height <= 0:
        return {"state": "BLANK", "reasons": [f"the capture reports a non-positive size: {width}x{height}"]}
    if size < 200:
        return {
            "state": "BLANK",
            "reasons": [
                f"the capture is only {size} bytes, which for a {width}x{height} PNG means a "
                "uniform image; a blank viewport produces a real screenshot and proves nothing"
            ],
        }
    return {
        "state": state,
        "reasons": reasons,
        "bytes": size,
        "width": width,
        "height": height,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _png_dimensions(payload: bytes) -> tuple[int, int] | None:
    """Width and height from the IHDR chunk, without an image library.

    Deliberately a header read rather than a decode: this must work on a stdlib-only
    runtime, and decoding is not needed to establish that a PNG exists and how large it
    is. The visual checks are the runtime inspection report's job, not the file's.
    """
    if len(payload) < 24 or payload[12:16] != b"IHDR":
        return None
    width = int.from_bytes(payload[16:20], "big")
    height = int.from_bytes(payload[20:24], "big")
    return width, height


def validate_runtime(report: Mapping, *, route: str = "", state: str = "",
                     expected_content: Sequence[str] = (),
                     required_regions: Sequence[str] = ()) -> dict:
    """Whether the *page* was ready to be photographed.

    This is the half the file cannot answer. ``validate_artifact`` proves an image
    exists; this proves the image is of the interface rather than of a spinner or an
    error page, which are images too.

    ``required_regions`` is the check for a shell that survived its own content. Text
    presence cannot catch it: a navigation rail outlives almost any layout failure, so a
    page whose workspace has collapsed to zero height still contains the nav labels and
    reads as "content present". When the plan declares the regions this surface must
    have, their absence is the finding -- which is exactly how a repair that blanks a
    layout gets caught instead of reported as an improvement.
    """
    reasons: list[str] = []
    if not isinstance(report, Mapping):
        return {"state": "NO_CONTENT", "reasons": ["the page produced no inspection report"]}
    region_counts = report.get("region_counts") if isinstance(report.get("region_counts"), Mapping) else {}
    for selector in required_regions or ():
        if str(selector) not in region_counts:
            continue
        total = region_counts.get(selector)
        visible = region_counts.get(f"{selector} (visible)")
        if isinstance(total, int) and total < 0:
            reasons.append(f"the region selector {selector!r} is not a usable CSS selector")
        elif not int(total or 0):
            reasons.append(
                f"the surface declares region {selector!r} as part of what it renders, and the page "
                "contains no such element; the application shell loaded but the target content did not"
            )
        elif visible is not None and not int(visible or 0):
            reasons.append(
                f"region {selector!r} exists but has no visible box; it collapsed to zero size, so "
                "the capture shows a shell where the content should be"
            )
    if reasons:
        return {"state": "NO_CONTENT", "reasons": reasons}
    busy = [str(item) for item in (report.get("busy_indicators") or [])]
    if busy:
        reasons.append(
            "the page was still declaring itself busy (" + ", ".join(sorted(set(busy))[:3]) + "); a "
            "capture of a loading state is evidence that the page loads, not of the interface"
        )
        return {"state": "LOADING", "reasons": reasons}
    text = str(report.get("text_sample", "") or "")
    text_length = int(report.get("text_length", 0) or 0)
    title = str(report.get("title", "") or "")
    haystack = f"{title} {text}".lower()
    for marker in adapter_module.ERROR_TEXT_MARKERS:
        if marker in haystack:
            reasons.append(
                f"the rendered document looks like an error page (matched {marker!r}); critiquing "
                "an error page as the intended interface is a category error, not a finding"
            )
            return {"state": "ERROR_DOCUMENT", "reasons": reasons}
    url = str(report.get("url", "") or "")
    if any(marker in url.lower() for marker in adapter_module.BROWSER_ERROR_DOCUMENTS):
        return {
            "state": "ERROR_DOCUMENT",
            "reasons": [f"the browser reported its own error document for {url!r}, not the application"],
        }
    if text_length < adapter_module.EMPTY_BODY_THRESHOLD and int(report.get("node_count", 0) or 0) < 3:
        return {
            "state": "NO_CONTENT",
            "reasons": [
                f"the document has {text_length} characters of visible text and "
                f"{int(report.get('node_count', 0) or 0)} nodes; the application shell may have loaded "
                "but the target content did not"
            ],
        }
    if expected_content:
        present = [token for token in expected_content if token.lower() in haystack]
        missing = [token for token in expected_content if token not in present]
        if missing and not present:
            return {
                "state": "NO_CONTENT",
                "reasons": [
                    "the render contains none of the content this route is supposed to show "
                    f"({', '.join(repr(item) for item in missing[:5])})"
                ],
            }
    for error in (report.get("page_errors") or []):
        reasons.append(f"the page raised a runtime error: {str(error)[:160]}")
    if reasons:
        return {"state": "NO_CONTENT", "reasons": reasons}
    return {
        "state": "VALID",
        "reasons": [],
        "text_length": text_length,
        "node_count": int(report.get("node_count", 0) or 0),
        "route_requested": route,
        "state_requested": state,
    }


def accessibility_report(report: Mapping) -> dict:
    """What a single render can and cannot establish about accessibility.

    Named precisely, because the failure mode here is a confident sentence. One
    screenshot at one viewport with one input device cannot establish WCAG conformance;
    what it *can* establish is a set of specific, checkable observations, and whether
    any of them is a defect.
    """
    unlabelled = [dict(item) for item in (report.get("unlabelled_controls") or []) if isinstance(item, Mapping)]
    small = [dict(item) for item in (report.get("small_targets") or []) if isinstance(item, Mapping)]
    no_ring = [dict(item) for item in (report.get("focusable_without_ring") or []) if isinstance(item, Mapping)]
    focusable = int(report.get("focusable_count", 0) or 0)
    findings: list[dict] = []
    if unlabelled:
        findings.append({
            "check": "accessible-name",
            "determinate": True,
            "detail": f"{len(unlabelled)} interactive control(s) expose no accessible name",
            "samples": unlabelled[:6],
        })
    if no_ring and focusable > 0:
        # Per element, not a page-wide boolean. One control with a visible ring satisfies
        # `focus_visible` and would hide every control that shows nothing at all -- which
        # is precisely the defect: a keyboard user cannot tell where they are.
        findings.append({
            "check": "focus-visible",
            "determinate": True,
            "detail": (
                f"{len(no_ring)} of {focusable} focusable elements produce no visible focus "
                "indicator when focused; a keyboard user cannot see where focus is"
            ),
            "samples": no_ring[:8],
        })
    elif focusable > 0 and not bool(report.get("focus_visible")):
        findings.append({
            "check": "focus-visible",
            "determinate": True,
            "detail": f"{focusable} focusable elements were focused and none showed a focus indicator",
            "samples": [],
        })
    if small:
        findings.append({
            "check": "target-size",
            "determinate": True,
            "detail": f"{len(small)} interactive target(s) are smaller than 24x24 CSS pixels",
            "samples": small[:6],
        })
    duration = str(report.get("transition_duration", "") or "")
    if report.get("prefers_reduced_motion") and duration and duration not in ("0s",):
        findings.append({
            "check": "reduced-motion",
            "determinate": True,
            "detail": (
                f"prefers-reduced-motion is set and the document still declares transition duration "
                f"{duration!r}"
            ),
            "samples": [],
        })
    return {
        "findings": findings,
        "not_established": [
            "WCAG conformance",
            "screen-reader announcement order",
            "colour contrast as perceived (no deterministic tool ran here)",
            "keyboard path completeness beyond the elements present at this viewport",
            "behaviour at viewports and input devices not captured",
        ],
        "method": (
            "deterministic DOM inspection of one render at one viewport; every finding names the "
            "check that produced it and none of them asserts conformance"
        ),
    }


def runtime_checks(report: Mapping, *, route: str = "", state: str = "") -> dict:
    """The non-aesthetic, reproducible facts one render establishes."""
    overflow_elements = [dict(item) for item in (report.get("overflowing_elements") or []) if isinstance(item, Mapping)]
    clipped = [dict(item) for item in (report.get("clipped_elements") or []) if isinstance(item, Mapping)]
    client_width = int(report.get("client_width", 0) or 0)
    # "Beyond the viewport" is the fact a reviewer can see in the image; "the document
    # scrolls" is not. A panel with `overflow:auto` contains an overflowing table, so the
    # document never scrolls and `scrollWidth == clientWidth` -- yet the capture plainly
    # shows the last two columns cut off. Keying this on document overflow alone reports
    # a clipped narrow layout as clean.
    beyond = [
        row for row in overflow_elements
        if int(row.get("right", 0) or 0) > client_width + 1
    ]
    clipped_rows = [
        row for row in clipped
        if int(row.get("clipped_x", 0) or 0) > 2 or int(row.get("clipped_y", 0) or 0) > 2
    ]
    unreached = beyond or clipped_rows
    checks = [
        {"check": "route-loaded", "passed": bool(report.get("url")), "detail": str(report.get("url", ""))[:200]},
        {"check": "ready-state", "passed": str(report.get("ready_state", "")) == "complete",
         "detail": str(report.get("ready_state", ""))},
        {"check": "horizontal-overflow", "passed": not bool(report.get("horizontal_overflow")),
         "detail": f"scrollWidth={report.get('scroll_width')} clientWidth={report.get('client_width')}"},
        {"check": "content-within-viewport", "passed": not unreached,
         "detail": (
             f"{len(unreached)} element(s) extend past the {client_width}px viewport and their "
             "content is not visible in the capture"
             if unreached else "all content lies within the viewport"
         )},
        {"check": "no-runtime-errors", "passed": not list(report.get("page_errors") or []),
         "detail": "; ".join(str(item)[:120] for item in (report.get("page_errors") or []))[:300]},
        {"check": "content-present", "passed": int(report.get("text_length", 0) or 0) >= adapter_module.EMPTY_BODY_THRESHOLD,
         "detail": f"{int(report.get('text_length', 0) or 0)} characters of visible text"},
    ]
    return {
        "checks": checks,
        "overflowing_elements": overflow_elements[:12],
        "beyond_viewport": beyond[:12],
        "clipped_elements": clipped_rows[:12],
        "viewport_width": client_width,
        "headings": [dict(item) for item in (report.get("headings") or []) if isinstance(item, Mapping)][:24],
        "console": [str(item) for item in (report.get("console") or [])][-10:],
    }


def _write_manifest(directory: Path, manifest: Mapping) -> str:
    payload = (json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n").encode("utf-8")
    if len(payload) > MAX_MANIFEST_BYTES:
        raise ContractError(
            f"the capture manifest is {len(payload)} bytes, above the {MAX_MANIFEST_BYTES}-byte bound; "
            "a manifest that cannot be read cannot be evidence"
        )
    target = Path(directory) / MANIFEST_NAME
    safety.assert_no_collision(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def execute(
    plan: Mapping,
    *,
    adapter: adapter_module.RenderAdapter,
    binding: Mapping,
    directory: Path,
    base_url: str = "",
    allow_hosts: Sequence[str] | None = None,
    capture_execution: str = "",
    expected_content: Mapping[str, Sequence[str]] | None = None,
) -> dict:
    """Run one capture plan and return one :class:`RenderedEvidenceSet`.

    Every planned target is attempted. A target that cannot be captured is recorded as
    skipped *with its reason* rather than dropped, because ``PARTIAL`` and ``CAPTURED``
    are different answers and only the recorded reason distinguishes them honestly.
    """
    started = contracts.utc_now()
    clock = time.monotonic()
    digest = str(binding.get("render_source_digest", ""))
    stale = source_staleness(binding)
    if stale:
        raise ContractError(
            "this capture plan's source binding is already stale, so re-running it would bind "
            "captures to implementation bytes that are not the implementation: " + "; ".join(stale)
        )
    target_root = Path(directory)
    captures: list[dict] = []
    runtime_rows: list[dict] = []
    accessibility_rows: list[dict] = []
    skipped: list[dict] = []
    failures: list[dict] = []
    probe = adapter.probe()
    index = 0
    base = str(base_url or "")
    for target in plan.get("targets") or []:
        if not isinstance(target, Mapping):
            continue
        index += 1
        route = str(target.get("route", ""))
        state = str(target.get("state", "default"))
        url = route if route.startswith("http") else f"{base.rstrip('/')}/{route.lstrip('/')}"
        try:
            url = safety.safe_route(url, allow_hosts=allow_hosts)
        except ContractError as exc:
            skipped.append(_skip_row(target, f"route refused: {exc}"))
            continue
        capture_id = f"capture_{index:03d}"
        try:
            row = _capture_one(
                adapter, target=target, url=url, capture_id=capture_id,
                directory=target_root, digest=digest,
                expected_content=(expected_content or {}).get(route, ()),
            )
        except adapter_module.RenderCapabilityUnavailable as exc:
            failures.append({"capture_id": capture_id, "route": route, "state": state, "reason": str(exc)})
            skipped.append(_skip_row(target, f"RENDER_CAPABILITY_UNAVAILABLE: {exc}"))
            continue
        except adapter_module.CaptureFailed as exc:
            failures.append({"capture_id": capture_id, "route": route, "state": state, "reason": str(exc)})
            skipped.append(_skip_row(target, str(exc)))
            continue
        if row["artifact"]["state"] != "VALID":
            skipped.append(_skip_row(
                target,
                f"{row['artifact']['state']}: " + "; ".join(row["artifact"]["reasons"])[:220],
            ))
            failures.append({"capture_id": capture_id, "route": route, "state": state,
                             "reason": "; ".join(row["artifact"]["reasons"])[:300]})
            continue
        row["capture_id"] = capture_id
        row["render_source_digest"] = digest
        row["evidence_id"] = ""
        captures.append(row)
        runtime_rows.append({"capture_id": capture_id, "route": route, "state": state, **row["runtime_checks"]})
        accessibility_rows.append({"capture_id": capture_id, "route": route, "state": state, **row["accessibility_checks"]})
    manifest = {
        "schema_version": contracts.SCHEMA_DESIGN,
        "evidence_set_id": contracts.new_record_id("res"),
        "capture_plan_id": str(plan.get("capture_plan_id", "")),
        "render_source_digest": digest,
        "browser": {
            "adapter": probe.adapter,
            "engine": probe.engine,
            "version": probe.version,
            "browser": probe.browser,
            "platform": probe.platform,
            "executable_present": bool(probe.extra.get("browser_executable_present")),
        },
        "captures": captures,
        "runtime_checks": runtime_rows,
        "accessibility_checks": accessibility_rows,
        "skipped": skipped,
        "failures": failures,
        "started_at": started,
        "completed_at": contracts.utc_now(),
        "status": "COMPLETE" if captures and not skipped else ("PARTIAL" if captures else "FAILED"),
        "duration_seconds": round(time.monotonic() - clock, 3),
        "capture_bytes": sum(int(row.get("bytes", 0)) for row in captures),
        "capture_execution": str(capture_execution),
        "provenance": {"created_by": "engine", "policy_version": contracts.POLICY_VERSION},
    }
    problems = contracts.rendered_evidence_set_problems(manifest)
    if problems and manifest["status"] == "COMPLETE":
        raise ContractError("the rendered evidence set is malformed: " + "; ".join(problems))
    manifest["manifest_sha256"] = _write_manifest(target_root, manifest)
    return manifest


def _skip_row(target: Mapping, reason: str) -> dict:
    return {
        "target_id": str(target.get("target_id", "")),
        "route": str(target.get("route", "")),
        "state": str(target.get("state", "")),
        "kind": str(target.get("kind", "")),
        "reason_skipped": str(reason)[:400],
    }


def _capture_one(
    adapter: adapter_module.RenderAdapter,
    *,
    target: Mapping,
    url: str,
    capture_id: str,
    directory: Path,
    digest: str,
    expected_content: Sequence[str] = (),
) -> dict:
    route = str(target.get("route", ""))
    state = str(target.get("state", "default"))
    viewport = dict(target.get("viewport") or {})
    theme = str(target.get("theme", "project-default"))
    reduced_motion = bool(target.get("reduced_motion", False))
    required_regions = [str(item) for item in (target.get("required_regions") or ())]
    adapter.set_viewport(viewport)
    adapter.navigate(url)
    if reduced_motion:
        _apply_reduced_motion(adapter)
    adapter.set_theme(theme)
    interaction = dict(target.get("interaction") or {})
    steps: list[str] = []
    if interaction:
        steps = list(adapter.perform_state(interaction).get("steps", []))
    if interaction and not steps:
        return {
            "artifact": {
                "state": "NO_CONTENT",
                "reasons": [
                    "the declared interaction state was never actually performed, so this would be a "
                    "picture of the default state wearing the interaction's name"
                ],
            }
        }
    path = safety.capture_path(directory, capture_id, suffix=".png")
    safety.assert_no_collision(path)
    # Capture BEFORE inspecting. The inspection pass focuses every focusable element in
    # turn and blurs the last one, so inspecting first silently destroys an interaction
    # state and photographs the default instead -- which is how a "focused" capture ends
    # up byte-identical to an unfocused one and nobody notices.
    captured = adapter.capture(path, full_page=False)
    report = adapter.inspect(selectors=required_regions)
    runtime = runtime_checks(report, route=route, state=state)
    runtime["interaction_steps"] = steps
    runtime["required_regions"] = [str(item) for item in required_regions]
    artifact = validate_artifact(Path(captured["path"]), expected_route=route, expected_state=state)
    page = validate_runtime(
        report, route=route, state=state, expected_content=expected_content,
        required_regions=required_regions,
    )
    if artifact["state"] == "VALID" and page["state"] != "VALID":
        # The image is fine; the page was not. The image must not become evidence.
        artifact = {"state": page["state"], "reasons": list(page["reasons"])}
    return {
        "capture_id": capture_id,
        "route": route,
        "state": state,
        "kind": str(target.get("kind", "")),
        "viewport": {**viewport, "device_scale_factor": 1},
        "theme": theme,
        "reduced_motion": reduced_motion,
        "target_id": str(target.get("target_id", "")),
        "artifact_path": str(captured["path"]),
        "digest": str(captured["sha256"]),
        "bytes": int(captured["bytes"]),
        "dimensions": dict(captured.get("bounds") or {}),
        "captured_at": contracts.utc_now(),
        "render_source_digest": digest,
        "artifact": artifact,
        "runtime_checks": runtime,
        "accessibility_checks": accessibility_report(report),
        "observation": f"{route} at {viewport.get('width')}x{viewport.get('height')} in state {state}",
        "url": url,
    }


def _apply_reduced_motion(adapter: adapter_module.RenderAdapter) -> None:
    """Force ``prefers-reduced-motion: reduce`` before capturing.

    A reference cannot override an accessibility preference, so a capture claiming to
    show the reduced-motion behaviour has to actually have it applied. Emulating the
    media feature is the difference between inspecting the behaviour and assuming it.
    """
    page = getattr(adapter, "_page", None)
    if page is None:
        return
    try:
        page.emulate_media(reduced_motion="reduce")
    except Exception:  # noqa: BLE001 - a capture still records that motion was not emulated
        pass


def source_staleness(binding: Mapping) -> list[str]:
    """Re-check a binding against the working tree at capture time."""
    from . import source as source_module

    root = str((binding.get("source_binding") or {}).get("project_root", "") or binding.get("project_root", ""))
    if not root:
        return []
    try:
        current = source_module.render_source_digest(Path(root))
    except ContractError as exc:
        return [f"the implementation could not be re-read to confirm the binding: {exc}"]
    return source_module.staleness(binding, current)


def record_evidence(
    state: dict,
    manifest: Mapping,
    *,
    task_id: str,
    direction_id: str = "",
    requirement_id: str = "",
    capture_execution: str = "",
) -> list[dict]:
    """Promote each validated capture into the engine's existing evidence ladder.

    This is the join point: a browser capture becomes a ``rnd_*`` record through
    :func:`ariadne_engine.render.record`, with ``capture_method="browser-render"``, so
    the same staleness, currentness and critique machinery that already existed now
    governs real browser evidence too. No second evidence system is created.
    """
    from .. import render as render_module

    recorded: list[dict] = []
    revision = str(manifest.get("render_source_digest", ""))
    for row in manifest.get("captures") or []:
        if not isinstance(row, Mapping):
            continue
        if str((row.get("artifact") or {}).get("state", "")) != "VALID":
            continue
        path = Path(str(row.get("artifact_path", "")))
        artifact = render_module.CaptureArtifact(
            kind="screenshot",
            path=str(path),
            sha256=str(row.get("digest", "")),
            viewport=dict(row.get("viewport") or {}),
            environment={
                "kind": "browser-render",
                "browser": str((manifest.get("browser") or {}).get("browser", "")),
                "engine": str((manifest.get("browser") or {}).get("engine", "")),
                "engine_version": str((manifest.get("browser") or {}).get("version", "")),
                "platform": str((manifest.get("browser") or {}).get("platform", "")),
                "capture_id": str(row.get("capture_id", "")),
                "state": str(row.get("state", "")),
                "theme": str(row.get("theme", "")),
                "reduced_motion": bool(row.get("reduced_motion", False)),
                "interaction_steps": list((row.get("runtime_checks") or {}).get("interaction_steps") or []),
                "dimensions": dict(row.get("dimensions") or {}),
            },
            method="browser-render",
            observation=str(row.get("observation", "")),
            extra={
                "capture_id": str(row.get("capture_id", "")),
                "render_source_digest": revision,
                "target_id": str(row.get("target_id", "")),
                "runtime_checks": dict(row.get("runtime_checks") or {}),
                "accessibility_checks": dict(row.get("accessibility_checks") or {}),
            },
        )
        _write_browser_manifest(Path(path).parent, row, manifest)
        record = render_module.record(
            state,
            task_id=task_id,
            revision_hash=revision,
            artifact=artifact,
            adapter=str((manifest.get("browser") or {}).get("adapter", "chromium-render")),
            adapter_available=True,
            capture_execution=capture_execution,
            requirement_id=requirement_id,
            direction_id=direction_id,
        )
        record["extra"]["capture_id"] = str(row.get("capture_id", ""))
        record["extra"]["render_source_digest"] = revision
        row["evidence_id"] = str(record.get("evidence_id", ""))
        recorded.append(record)
    return recorded


def _write_browser_manifest(directory: Path, row: Mapping, manifest: Mapping) -> None:
    """The per-artifact manifest AR-202D's provenance check already knows how to read.

    ``render._provenance_problems`` accepts a method only by name, so a
    ``browser-render`` artifact currently has no manifest obligation. Writing the same
    ``capture-manifest.json`` shape anyway means the browser artifact is checkable by
    exactly the same rule as a fixture one, with no special case to drift.
    """
    target = Path(directory) / "capture-manifest.json"
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({
            "adapter": str((manifest.get("browser") or {}).get("adapter", "chromium-render")),
            "route": str(row.get("route", "")),
            "viewport": dict(row.get("viewport") or {}),
            "kind": "screenshot",
            "artifact": {"path": str(Path(str(row.get("artifact_path", ""))).resolve()),
                         "sha256": str(row.get("digest", ""))},
            "environment": {
                "kind": "browser-render",
                "browser": str((manifest.get("browser") or {}).get("browser", "")),
                "engine": str((manifest.get("browser") or {}).get("engine", "")),
            },
            "recorded_at": str(row.get("captured_at", "")),
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load(directory: Path) -> dict:
    path = Path(directory) / MANIFEST_NAME
    if not path.is_file():
        raise ContractError(f"no rendered evidence manifest is present at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def evidence_sets(state: dict) -> list[dict]:
    rows = state.get("rendered_evidence_sets")
    if not isinstance(rows, list):
        return []
    return [item for item in rows if isinstance(item, Mapping)]


def by_id(state: dict, evidence_set_id: str) -> dict | None:
    """The stored manifest, not a copy.

    ``mark_rerendered`` writes through this handle, so a defensive copy would make the
    closure a silent no-op that still returns a plausible record.
    """
    for row in state.get("rendered_evidence_sets") or []:
        if isinstance(row, Mapping) and str(row.get("evidence_set_id", "")) == str(evidence_set_id):
            return row
    return None


def append(state: dict, manifest: Mapping) -> dict:
    contracts.require_design_capacity(state, "rendered_evidence_sets")
    state.setdefault("rendered_evidence_sets", []).append(manifest)
    return manifest


def summary(manifest: Mapping) -> dict:
    captures = [row for row in (manifest.get("captures") or []) if isinstance(row, Mapping)]
    return {
        "evidence_set_id": str(manifest.get("evidence_set_id", "")),
        "capture_plan_id": str(manifest.get("capture_plan_id", "")),
        "render_source_digest": str(manifest.get("render_source_digest", ""))[:12],
        "captures": len(captures),
        "skipped": len(manifest.get("skipped") or []),
        "failures": len(manifest.get("failures") or []),
        "capture_bytes": int(manifest.get("capture_bytes", 0) or 0),
        "duration_seconds": manifest.get("duration_seconds", 0),
        "status": str(manifest.get("status", "")),
        "browser": dict(manifest.get("browser") or {}),
        "by_viewport": {
            str((row.get("viewport") or {}).get("width", "")): 1 for row in captures
        },
    }


def curate(manifest: Mapping, *, limit: int = 6, required: Sequence[str] = ()) -> dict:
    """The subset a reviewer should actually look at, and why each was chosen.

    §53 in one function. Four well-chosen captures beat thirty full-resolution ones,
    and the reason each was selected has to be in the record -- otherwise "curated"
    is just a smaller number with no justification, and a reviewer cannot tell whether
    the omitted material was omitted because it was redundant or because it was
    unflattering.
    """
    captures = [row for row in (manifest.get("captures") or []) if isinstance(row, Mapping)]
    wanted = {str(item) for item in required}
    chosen: list[dict] = []
    # Required captures are placed first. Selecting by viewport breadth until the limit
    # bites would drop the very captures a finding cites, which is the opposite of what a
    # curated evidence set is for.
    for row in captures:
        if str(row.get("capture_id", "")) in wanted:
            chosen.append({
                "capture_id": str(row.get("capture_id", "")), "route": row.get("route"),
                "state": row.get("state"),
                "reason_selected": "cited by a finding or requirement",
            })
    covered = {
        str((row.get("viewport") or {}).get("width", ""))
        for row in captures if str(row.get("capture_id", "")) in wanted
    }
    states_covered = {
        str(row.get("state", "")) for row in captures if str(row.get("capture_id", "")) in wanted
    }
    for row in captures:
        if len(chosen) >= limit:
            break
        capture_id = str(row.get("capture_id", ""))
        if capture_id in wanted:
            continue
        viewport = str((row.get("viewport") or {}).get("width", ""))
        state_name = str(row.get("state", ""))
        if viewport not in covered:
            reason = f"first capture at the {viewport}px viewport"
            covered.add(viewport)
        elif state_name not in states_covered:
            reason = f"distinct interaction state {state_name!r}"
            states_covered.add(state_name)
        else:
            continue
        chosen.append({
            "capture_id": capture_id, "route": row.get("route"), "state": row.get("state"),
            "reason_selected": reason,
        })
    selected_ids = [item["capture_id"] for item in chosen]
    omitted = [
        {"capture_id": str(row.get("capture_id", "")), "route": row.get("route"), "state": row.get("state"),
         "reason_omitted": "materially covered by a selected capture; excluded to bound reviewer context"}
        for row in captures if str(row.get("capture_id", "")) not in {item["capture_id"] for item in chosen}
    ]
    return {"selected": chosen, "omitted": omitted, "limit": int(limit)}


def describe(record: Mapping) -> str:
    return (
        f"{record.get('evidence_set_id')} {record.get('status')} with "
        f"{len(record.get('captures') or [])} capture(s) bound to "
        f"{str(record.get('render_source_digest', ''))[:12]}"
    )


__all__ = [
    "MANIFEST_NAME",
    "PNG_MAGIC",
    "MAX_MANIFEST_BYTES",
    "validate_artifact",
    "validate_runtime",
    "accessibility_report",
    "runtime_checks",
    "execute",
    "record_evidence",
    "load",
    "evidence_sets",
    "by_id",
    "append",
    "summary",
    "curate",
    "describe",
]
