"""The render adapter: a real browser behind a vendor-neutral contract (AR-222).

AR-200 recorded "real browser tooling" as an ADD, and AR-202D shipped the honest
unavailable stub :class:`ariadne_engine.render.LocalBrowserAdapter`. This module
fills that seam without making any browser vendor the conceptual contract.

The abstraction is the eight operations that *any* rendering surface can be asked for:
probe, launch, navigate, set_viewport, set_theme, perform_state, capture, inspect,
shutdown. Everything above this line -- plans, evidence sets, critique, refinement --
speaks only in those terms. Swapping Chromium for anything else is a new adapter, not
a rewrite, and a plan that says "1440x900 at /workspace with a focus state" does not
change.

Three decisions worth stating because they are the ones that make this trustworthy:

**Playwright is optional and never imported at module load.** Ariadne ships
``dependencies = []`` and that is not negotiable. The probe is a ``find_spec`` and a
version string; if playwright is not importable the adapter reports
``RENDER_CAPABILITY_UNAVAILABLE`` and the run says so. Nothing degrades to source
inspection while still reporting a visual review.

**A failed capture is a named refusal, never a fallback.** :class:`CaptureFailed` and
:class:`RenderCapabilityUnavailable` are distinct exceptions so the caller can answer
"the environment could not render" differently from "the page did not render".

**Every navigation is validated before the browser is told anything.** A route is
attacker-influenced input arriving from a capture plan; the adapter routes it through
:mod:`ariadne_engine.rendered_critique.safety` first, so an adapter author cannot
forget.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .. import contracts
from ..contracts import ContractError
from . import safety

DEFAULT_NAVIGATION_TIMEOUT_MS = 20000
DEFAULT_SETTLE_MS = 350
LAUNCH_ATTEMPTS = 3
LAUNCH_RETRY_SECONDS = 1.5
SERVER_READY_TIMEOUT_SECONDS = 20.0
SERVER_POLL_SECONDS = 0.1
BROWSER_EXIT_SECONDS = 5.0
"""How long shutdown waits for the browser process to exit.

Bounded, because shutdown must not become a hang. The wait exists so the operating
system has released the files the browser had mapped before a caller deletes them; without
it, cleanup of a directory the browser was serving fails intermittently and the failure
lands on an unrelated test.
"""
"""How long a freshly spawned surface server is given to begin listening.

``Popen`` returning is not the server being ready. Waiting for the port is the difference
between a capture of the surface and a capture of a connection error, and the second looks
exactly like the first in a PNG until something reads it.
"""
"""Bounded launch retry. Narrow on purpose -- see :meth:`ChromiumRenderAdapter.launch`.

Retrying is only honest because the retried operation produces no evidence: a browser that
failed to start captured nothing, so there is nothing to launder. Navigation, capture and
inspection are never retried.
"""
MAX_STATE_DEPTH = 8
"""Bounded interaction steps. A capture that drives a thousand actions is a test, not
an inspection, and would make the capture budget meaningless."""

LOADING_SELECTORS = (
    "[aria-busy='true']", "[data-loading='true']", "[data-testid='loading']",
    ".loading", ".spinner", "[role='progressbar']",
)
"""Signals that the page has not finished arriving. Used to refuse a screenshot of a
spinner, which is the single most common way a broken page produces confident
evidence."""

ERROR_TEXT_MARKERS = (
    "internal server error", "500 internal", "404 not found", "502 bad gateway",
    "503 service unavailable", "504 gateway", "traceback (most recent call last)",
    "uncaught (in promise)", "something went wrong", "application error",
)
"""Text that marks a document as an error page. Refusing these matters more than it
looks: an error page is usually *legible and well laid out*, so a reviewer with no
check would critique it as if it were the intended interface."""

BROWSER_ERROR_DOCUMENTS = ("chrome-error://", "chromewebdata", "about:neterror", "error page")
EMPTY_BODY_THRESHOLD = 24
"""Characters of visible text below which a document is treated as blank. A viewport
of background colour is a real failure mode and produces a real PNG."""


class RenderCapabilityUnavailable(ContractError):
    """No rendering capability is available here. Never silently degraded."""


class CaptureFailed(ContractError):
    """A rendering capability existed and the capture did not succeed."""


@dataclass(frozen=True)
class ProbeResult:
    """What a capability probe established, and how it established it."""

    available: bool
    mechanism: str
    reason: str
    adapter: str = "chromium-render"
    engine: str = ""
    version: str = ""
    browser: str = ""
    platform: str = ""
    extra: Mapping[str, object] = field(default_factory=dict)

    def as_record(self) -> dict:
        return {
            "adapter": self.adapter,
            "available": self.available,
            "mechanism": self.mechanism,
            "reason": self.reason,
            "engine": self.engine,
            "version": self.version,
            "browser": self.browser,
            "platform": self.platform,
            **dict(self.extra),
        }


@dataclass
class CaptureResult:
    """One capture: the artifact on disk plus the facts that make it reviewable."""

    capture_id: str
    route: str
    state: str
    viewport: Mapping[str, object]
    theme: str
    artifact_path: str
    digest: str
    bytes: int
    captured_at: str
    dimensions: Mapping[str, object]
    browser: Mapping[str, object]
    runtime_checks: Mapping[str, object]
    accessibility_checks: Mapping[str, object]
    observation: str = ""
    notes: str = ""


class RenderAdapter:
    """The vendor-neutral contract. Subclasses implement the eight operations."""

    id = "abstract-render"

    def probe(self) -> ProbeResult:
        raise RenderCapabilityUnavailable(f"render adapter {self.id!r} has no probe")

    def launch(self) -> None:
        raise RenderCapabilityUnavailable(f"render adapter {self.id!r} cannot launch")

    def navigate(self, url: str) -> None:
        raise RenderCapabilityUnavailable(f"render adapter {self.id!r} cannot navigate")

    def set_viewport(self, viewport: Mapping) -> None:
        raise RenderCapabilityUnavailable(f"render adapter {self.id!r} cannot set a viewport")

    def set_theme(self, theme: str) -> None:
        raise RenderCapabilityUnavailable(f"render adapter {self.id!r} cannot set a theme")

    def perform_state(self, descriptor: Mapping) -> dict:
        raise RenderCapabilityUnavailable(f"render adapter {self.id!r} cannot perform a state")

    def capture(self, path: Path, *, full_page: bool = False) -> dict:
        raise RenderCapabilityUnavailable(f"render adapter {self.id!r} cannot capture")

    def inspect(self) -> dict:
        raise RenderCapabilityUnavailable(f"render adapter {self.id!r} cannot inspect")

    def shutdown(self) -> None:
        raise RenderCapabilityUnavailable(f"render adapter {self.id!r} cannot shut down")

    # -- convenience ---------------------------------------------------------
    def available(self) -> tuple[bool, str]:
        probe = self.probe()
        return probe.available, probe.reason

    def capabilities(self) -> tuple[str, ...]:
        return ("screenshot", "dom", "browser", "measurement", "interaction", "accessibility", "console")

    def capability_record(self) -> dict:
        return self.probe().as_record()


def probe_playwright() -> ProbeResult:
    """Establish whether a real rendering engine exists here, and say how.

    The mechanism string starts with ``probe:`` because the capability registry
    requires evidence for anything at or above ``AVAILABLE``. A hand-written
    "chromium is probably installed" would be exactly the kind of assertion this
    repository has spent several milestones refusing.
    """
    import sys

    spec = importlib.util.find_spec("playwright")
    if spec is None:
        return ProbeResult(
            available=False,
            mechanism="probe:importlib.find_spec",
            reason=(
                "the playwright package is not importable in this interpreter; Ariadne does not "
                "install it, and a rendered review cannot be produced from source inspection"
            ),
        )
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415 - deliberately lazy
    except Exception as exc:  # noqa: BLE001 - any import failure is an unavailability
        return ProbeResult(
            available=False,
            mechanism="probe:importlib.import_module",
            reason=f"playwright is present but not importable: {exc}",
        )
    try:
        version = getattr(__import__("playwright"), "__version__", "") or "unknown"
    except Exception:  # noqa: BLE001 - version is cosmetic
        version = "unknown"
    executable = _chromium_executable()
    return ProbeResult(
        available=True,
        mechanism="probe:playwright.sync_api",
        reason="",
        engine="playwright",
        version=str(version),
        browser="chromium",
        platform=f"{sys.platform}",
        extra={
            "module_path": str(getattr(spec, "origin", "") or ""),
            "browser_executable": executable,
            "browser_executable_present": bool(executable and Path(executable).exists()),
        },
    )


def _chromium_executable() -> str:
    """A browser binary, if one is present. Reported, never installed."""
    for name in ("msedge", "chrome", "chromium", "chromium-browser"):
        located = shutil.which(name)
        if located:
            return located
    for candidate in (
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ):
        if Path(candidate).is_file():
            return candidate
    return ""


class ChromiumRenderAdapter(RenderAdapter):
    """A real browser rendering surface.

    Playwright is imported lazily inside :meth:`launch`, so importing this module --
    or Ariadne itself -- never requires a browser. If the import fails at launch the
    adapter reports :class:`RenderCapabilityUnavailable` rather than degrading.
    """

    id = "chromium-render"

    def __init__(
        self,
        *,
        run_root: Path,
        launch_command: Sequence[str] = (),
        allow_hosts: Sequence[str] | None = None,
        navigation_timeout_ms: int = DEFAULT_NAVIGATION_TIMEOUT_MS,
        settle_ms: int = DEFAULT_SETTLE_MS,
        headless: bool = True,
    ) -> None:
        self.run_root = Path(run_root)
        self.launch_command = safety.safe_launch_command(launch_command, working_root=self.run_root)
        self.allow_hosts = tuple(allow_hosts) if allow_hosts is not None else safety.DEFAULT_ALLOWED_HOSTS
        self.navigation_timeout_ms = int(navigation_timeout_ms)
        self.settle_ms = int(settle_ms)
        self.headless = bool(headless)
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._probe = ProbeResult(
            available=False, mechanism="probe:not-run",
            reason="the adapter has not been probed yet",
        )
        self._console: list[str] = []
        self._page_errors: list[str] = []
        self._viewport: dict[str, object] = {"width": 1440, "height": 900, "device_scale_factor": 1}
        self.launch_retries = 0
        self._lock = threading.Lock()

    # -- contract ------------------------------------------------------------
    def probe(self) -> ProbeResult:
        self._probe = probe_playwright()
        return self._probe

    def available(self) -> tuple[bool, str]:
        probe = self.probe()
        if not probe.available:
            return False, probe.reason
        if not probe.extra.get("browser_executable_present"):
            return False, (
                "playwright is importable but no chromium-family browser binary is present; "
                "Ariadne will not install one"
            )
        return True, ""

    def launch(self) -> None:
        """Start the browser, retrying a transient launch failure a bounded number of times.

        The retry is deliberately narrow: it wraps *starting a browser process* and nothing
        else. Starting a browser is not the behaviour under test here -- capturing pixels is
        -- and under a loaded release gate (five suites before it, each launching Chromium,
        then forty whole suite re-runs) the driver occasionally fails to start on the first
        attempt. Retrying a launch cannot weaken any guarantee in this phase, because every
        capture, validation and refusal still runs exactly once and any repeated launch
        failure surfaces as the same named refusal.

        What is *not* retried: navigation, capture, or inspection. Those are the operations
        whose outcomes are evidence, and retrying them would launder a real failure into a
        success.
        """
        available, reason = self.available()
        if not available:
            raise RenderCapabilityUnavailable(
                f"RENDER_CAPABILITY_UNAVAILABLE: {reason}"
            )
        try:
            from playwright.sync_api import sync_playwright  # noqa: PLC0415 - deliberately lazy
        except Exception as exc:  # noqa: BLE001
            raise RenderCapabilityUnavailable(
                f"RENDER_CAPABILITY_UNAVAILABLE: playwright could not be imported: {exc}"
            ) from exc
        executable = str(self._probe.extra.get("browser_executable", "") or "")
        last = ""
        for attempt in range(1, LAUNCH_ATTEMPTS + 1):
            try:
                self._playwright = sync_playwright().start()
                self._browser = self._playwright.chromium.launch(
                    headless=self.headless,
                    executable_path=executable or None,
                    args=["--disable-gpu", "--no-sandbox", "--hide-scrollbars"],
                    timeout=45000,
                )
                self._context = self._browser.new_context(
                    viewport={"width": 1440, "height": 900}, device_scale_factor=1,
                )
                self._context.set_default_timeout(self.navigation_timeout_ms)
                self._page = self._context.new_page()
                self._page.on("console", lambda message: self._console.append(str(getattr(message, "text", ""))))
                self._page.on("pageerror", lambda error: self._page_errors.append(str(error)))
                if attempt > 1:
                    self.launch_retries = attempt - 1
                return
            except Exception as exc:  # noqa: BLE001 - a launch failure is a named refusal
                last = f"{type(exc).__name__}: {exc}"
                self.shutdown()
                if attempt < LAUNCH_ATTEMPTS:
                    time.sleep(LAUNCH_RETRY_SECONDS * attempt)
        raise CaptureFailed(
            f"CAPTURE_FAILED: the browser could not be launched after {LAUNCH_ATTEMPTS} "
            f"attempts: {last}"
        )

    def navigate(self, url: str) -> None:
        page = self._require_page()
        safe = safety.safe_route(url, allow_hosts=self.allow_hosts)
        try:
            response = page.goto(safe, wait_until="networkidle", timeout=self.navigation_timeout_ms)
        except Exception as exc:  # noqa: BLE001
            raise CaptureFailed(f"CAPTURE_FAILED: {safe} did not load: {exc}") from exc
        if response is not None and int(getattr(response, "status", 0) or 0) >= 400:
            raise CaptureFailed(
                f"CAPTURE_FAILED: {safe} returned HTTP {getattr(response, 'status', '?')}; an error "
                "response is not the intended interface"
            )

    def set_viewport(self, viewport: Mapping) -> None:
        page = self._require_page()
        width = int(dict(viewport).get("width", 0) or 0)
        height = int(dict(viewport).get("height", 0) or 0)
        if width <= 0 or height <= 0:
            raise CaptureFailed(f"CAPTURE_FAILED: viewport {width}x{height} is not a usable size")
        self._viewport = {"width": width, "height": height, "device_scale_factor": 1}
        page.set_viewport_size({"width": width, "height": height})

    def set_theme(self, theme: str) -> None:
        page = self._require_page()
        name = str(theme or "").strip()
        if not name or name == "project-default":
            # The project's own default is the only theme that needs no override.
            # Manufacturing a dark mode because a reference had one would be inventing
            # a requirement, so this is a deliberate no-op rather than a guess.
            return
        try:
            page.evaluate(
                "(name) => { document.documentElement.setAttribute('data-theme', name);"
                " document.documentElement.classList.toggle('dark', name === 'dark'); }",
                name,
            )
        except Exception as exc:  # noqa: BLE001
            raise CaptureFailed(f"CAPTURE_FAILED: theme {name!r} could not be applied: {exc}") from exc

    def perform_state(self, descriptor: Mapping) -> dict:
        page = self._require_page()
        action = safety.safe_action(descriptor)
        kind = str(action["kind"])
        selector = str(action.get("selector", "") or "")
        steps: list[str] = []
        with self._lock:
            if kind == "hover" and selector:
                page.hover(selector)
                steps.append(f"hovered {selector}")
            elif kind == "focus" and selector:
                page.focus(selector)
                steps.append(f"focused {selector}")
            elif kind == "click" and selector:
                page.click(selector)
                steps.append(f"clicked {selector}")
            elif kind == "press":
                key = str(action.get("key", ""))
                if selector:
                    page.focus(selector)
                    steps.append(f"focused {selector}")
                page.keyboard.press(key)
                steps.append(f"pressed {key}")
            elif kind == "select" and selector:
                page.select_option(selector, str(action.get("value", "")))
                steps.append(f"selected {action.get('value', '')} in {selector}")
            elif kind == "navigate":
                self.navigate(str(action.get("value", "")))
                steps.append(f"navigated to {action.get('value', '')}")
            elif kind == "set_viewport":
                self.set_viewport(dict(action.get("viewport") or {}))
                steps.append("viewport set")
            elif kind == "evaluate_readonly":
                value = page.evaluate(f"() => ({action['expression']})")
                steps.append(f"read {action['expression']} = {json.dumps(value, default=str)[:200]}")
            else:
                raise CaptureFailed(f"CAPTURE_FAILED: interaction {kind!r} has nothing to act on")
            self._settle()
        return {"kind": kind, "steps": steps, "action": action}

    def capture(self, path: Path, *, full_page: bool = False) -> dict:
        import hashlib

        page = self._require_page()
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            raw = page.screenshot(full_page=bool(full_page))
        except Exception as exc:  # noqa: BLE001
            raise CaptureFailed(f"CAPTURE_FAILED: no image could be produced: {exc}") from exc
        if not raw:
            raise CaptureFailed("CAPTURE_FAILED: the browser produced an empty image")
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            raise CaptureFailed(
                "CAPTURE_FAILED: the browser produced bytes that are not a PNG; a file with a "
                "screenshot name is not a screenshot"
            )
        target.write_bytes(raw)
        bounds = safety.bound_image(
            int(self._viewport.get("width", 0) or 0),
            int(self._viewport.get("height", 0) or 0),
            bytes_written=len(raw),
            full_page=bool(full_page),
            viewport_height=int(self._viewport.get("height", 0) or 0),
        )
        return {
            "path": str(target.resolve()),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "bounds": bounds,
        }

    def inspect(self, selectors: Sequence[str] = ()) -> dict:
        """Measure the page. Optional selectors are counted as structural regions.

        Region counts are how a shell-only render is told apart from a real one. Text
        presence is not enough: a navigation rail survives almost any layout failure, so
        a page whose entire workspace has collapsed still contains the words "Request"
        and "History" and would sail through a content check. Counting the regions the
        plan says this surface must have is what catches it.
        """
        page = self._require_page()
        try:
            # INSPECT_SCRIPT is already interpolated at module level; applying % again
            # would raise "not all arguments converted".
            report = page.evaluate(
                INSPECT_SCRIPT, {"selectors": [str(item) for item in selectors if str(item).strip()]},
            )
        except Exception as exc:  # noqa: BLE001
            raise CaptureFailed(f"CAPTURE_FAILED: the page could not be inspected: {exc}") from exc
        report["console"] = list(self._console[-40:])
        report["page_errors"] = list(self._page_errors[-20:])
        return report

    def shutdown(self) -> None:
        """Stop the browser and wait for it to actually be gone.

        Best-effort teardown is not good enough here. ``close()`` asks the browser to
        exit; the operating system may still hold handles on the files it had mapped for
        a short while afterwards. A caller that then deletes a directory the browser was
        serving fails with a sharing violation, and the failure lands on whichever test
        happens to be cleaning up -- which reads as an intermittent behavioural failure
        rather than as a teardown race.

        So: close everything, then wait, bounded, for the driver process to exit.
        """
        for closer in (getattr(self._context, "close", None), getattr(self._browser, "close", None),
                       getattr(self._playwright, "stop", None)):
            if closer is None:
                continue
            try:
                closer()
            except Exception:  # noqa: BLE001 - shutdown must not mask the real error
                pass
        self._page = self._context = self._browser = self._playwright = None
        self._await_browser_exit()

    def _await_browser_exit(self) -> None:
        """Give the engine process a bounded moment to release its file handles."""
        deadline = time.monotonic() + BROWSER_EXIT_SECONDS
        while time.monotonic() < deadline:
            process = self._driver_process()
            if process is None:
                return
            try:
                if process.poll() is not None:
                    return
            except Exception:  # noqa: BLE001 - introspection is best effort
                return
            time.sleep(0.05)

    def _driver_process(self):
        """The browser's process handle, if the engine exposes one."""
        for holder in (self._browser, self._playwright):
            process = getattr(holder, "process", None)
            if process is not None and hasattr(process, "poll"):
                return process
        return None

    # -- internals -----------------------------------------------------------
    def _require_page(self) -> Any:
        if self._page is None:
            raise RenderCapabilityUnavailable(
                "RENDER_CAPABILITY_UNAVAILABLE: no page is open; launch() must succeed before capture"
            )
        return self._page

    def _settle(self) -> None:
        page = self._page
        if page is None:  # pragma: no cover - guarded by caller
            return
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:  # noqa: BLE001 - a settled-enough page is acceptable
            pass
        try:
            page.wait_for_timeout(self.settle_ms)
        except Exception:  # noqa: BLE001
            pass

    def __enter__(self) -> "ChromiumRenderAdapter":
        self.launch()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.shutdown()


INSPECT_SCRIPT = """
(arg) => {
  const wanted = (arg && arg.selectors) || [];
  const text = (document.body && document.body.innerText || '').trim();
  const html = document.documentElement ? document.documentElement.outerHTML : '';
  const busy = [];
  for (const selector of %s) {
    for (const node of document.querySelectorAll(selector)) {
      const rect = node.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) { busy.push(selector); break; }
    }
  }
  const scrollWidth = document.documentElement.scrollWidth;
  const clientWidth = document.documentElement.clientWidth;
  const overflow = [];
  for (const node of Array.from(document.body ? document.body.querySelectorAll('*') : [])) {
    const rect = node.getBoundingClientRect();
    if (rect.width > 0 && rect.right > clientWidth + 1.5) {
      overflow.push({
        tag: (node.tagName || '').toLowerCase(),
        right: Math.round(rect.right),
        width: Math.round(rect.width),
        cls: String(node.className || '').slice(0, 80),
      });
    }
    if (overflow.length >= 12) { break; }
  }
  const focusable = document.querySelectorAll(
    'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  const focusSamples = [];
  const noRing = [];
  for (const node of Array.from(focusable).slice(0, 40)) {
    node.focus();
    const style = window.getComputedStyle(node);
    const outline = style.outlineStyle;
    const hasOutline = outline && outline !== 'none' && parseFloat(style.outlineWidth || '0') > 0;
    const hasShadow = style.boxShadow && style.boxShadow !== 'none';
    const ring = hasOutline || hasShadow;
    const cls = String(node.className || '').slice(0, 60);
    const label = (node.getAttribute('aria-label') || (node.textContent || '').trim() ||
      String(node.getAttribute('type') || '')).slice(0, 40);
    focusSamples.push({ ring: ring, tag: (node.tagName || '').toLowerCase(), cls: cls, label: label });
    if (!ring) {
      // Per element, not a page-wide boolean. A single global "did anything show a
      // ring" is satisfied by one well-styled control and hides every control that
      // shows nothing, which is exactly the defect worth catching.
      noRing.push({
        tag: (node.tagName || '').toLowerCase(),
        cls: cls,
        label: label,
      });
    }
  }
  if (document.activeElement && document.body) { document.activeElement.blur(); }
  const clipped = [];
  for (const node of Array.from(document.querySelectorAll('*')).slice(0, 900)) {
    const style = window.getComputedStyle(node);
    const hides = style.overflow === 'hidden' || style.overflowX === 'hidden' || style.overflowY === 'hidden';
    if (!hides) { continue; }
    const dx = node.scrollWidth - node.clientWidth;
    const dy = node.scrollHeight - node.clientHeight;
    if (dx > 2 || dy > 2) {
      clipped.push({
        tag: (node.tagName || '').toLowerCase(),
        cls: String(node.className || '').slice(0, 60),
        clipped_x: dx,
        clipped_y: dy,
        client_width: node.clientWidth,
        scroll_width: node.scrollWidth,
      });
    }
    if (clipped.length >= 10) { break; }
  }
  const headings = [];
  for (const node of Array.from(document.querySelectorAll('h1, h2, h3'))) {
    const rect = node.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      headings.push({
        tag: (node.tagName || '').toLowerCase(),
        text: (node.textContent || '').trim().slice(0, 60),
        cls: String(node.className || '').slice(0, 60),
      });
    }
  }
  const unlabelled = [];
  for (const node of Array.from(document.querySelectorAll('button, a, input, select, textarea')).slice(0, 60)) {
    const tag = (node.tagName || '').toLowerCase();
    const name = node.getAttribute('aria-label') || node.getAttribute('title') ||
      (node.textContent || '').trim() ||
      (node.labels && node.labels.length ? node.labels[0].textContent.trim() : '') ||
      (node.getAttribute('aria-labelledby') ? 'by-id' : '');
    if (!name) {
      unlabelled.push({ tag: tag, cls: String(node.className || '').slice(0, 60) });
    }
  }
  const smallTargets = [];
  for (const node of Array.from(document.querySelectorAll('button, a[href], [role=button], input')).slice(0, 60)) {
    const rect = node.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0 && (rect.width < 24 || rect.height < 24)) {
      smallTargets.push({
        tag: (node.tagName || '').toLowerCase(),
        w: Math.round(rect.width), h: Math.round(rect.height),
      });
    }
  }
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const duration = getComputedStyle(document.body || document.documentElement).transitionDuration;
  const regionCounts = {};
  for (const selector of wanted) {
    let count = 0;
    let visible = 0;
    try {
      for (const node of Array.from(document.querySelectorAll(selector))) {
        count += 1;
        const rect = node.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) { visible += 1; }
      }
    } catch (error) {
      regionCounts[selector] = -1;
      continue;
    }
    regionCounts[selector] = count;
    regionCounts[selector + ' (visible)'] = visible;
  }
  return {
    url: location.href,
    title: document.title || '',
    text_length: text.length,
    text_sample: text.slice(0, 400),
    node_count: document.querySelectorAll('*').length,
    html_length: html.length,
    busy_indicators: busy,
    scroll_width: scrollWidth,
    client_width: clientWidth,
    horizontal_overflow: scrollWidth > clientWidth + 1,
    overflowing_elements: overflow,
    focusable_count: focusable.length,
    focus_visible: focusSamples.some((sample) => sample.ring),
    focusable_without_ring: noRing,
    focus_samples: focusSamples,
    unlabelled_controls: unlabelled,
    small_targets: smallTargets,
    clipped_elements: clipped,
    headings: headings,
    region_counts: regionCounts,
    prefers_reduced_motion: prefersReduced,
    transition_duration: duration,
    ready_state: document.readyState,
  };
}
""" % json.dumps(list(LOADING_SELECTORS))


class UnavailableRenderAdapter(RenderAdapter):
    """The adapter that exists when no browser does.

    It is a real object with a real refusal rather than a missing attribute, so the
    failure path is exercised on every run instead of only on the machines that lack a
    browser. Every operation raises the same named refusal, so a caller cannot
    accidentally treat "no browser" as "nothing to do here".
    """

    id = "unavailable-render"

    def __init__(self, reason: str = "") -> None:
        self._reason = reason or (
            "no rendering capability is configured for this run; a rendered review cannot be "
            "produced, and source inspection is not a substitute for one"
        )

    def probe(self) -> ProbeResult:
        return ProbeResult(
            available=False, mechanism="probe:declared-unavailable",
            reason=self._reason, adapter=self.id,
        )

    def available(self) -> tuple[bool, str]:
        return False, self._reason

    def launch(self) -> None:
        raise RenderCapabilityUnavailable(f"RENDER_CAPABILITY_UNAVAILABLE: {self._reason}")

    # Every remaining operation refuses by name. These are written out rather than
    # synthesised in ``__getattr__`` because the base class already defines them, so
    # attribute lookup finds the base method and ``__getattr__`` never runs -- which would
    # leave a caller holding a method that raises TypeError instead of the named refusal
    # it is supposed to get.
    def navigate(self, url: str) -> None:
        raise RenderCapabilityUnavailable(f"RENDER_CAPABILITY_UNAVAILABLE: {self._reason}")

    def set_viewport(self, viewport: Mapping) -> None:
        raise RenderCapabilityUnavailable(f"RENDER_CAPABILITY_UNAVAILABLE: {self._reason}")

    def set_theme(self, theme: str) -> None:
        raise RenderCapabilityUnavailable(f"RENDER_CAPABILITY_UNAVAILABLE: {self._reason}")

    def perform_state(self, descriptor: Mapping) -> dict:
        raise RenderCapabilityUnavailable(f"RENDER_CAPABILITY_UNAVAILABLE: {self._reason}")

    def capture(self, path: Path, *, full_page: bool = False) -> dict:
        raise RenderCapabilityUnavailable(f"RENDER_CAPABILITY_UNAVAILABLE: {self._reason}")

    def inspect(self, selectors: Sequence[str] = ()) -> dict:
        raise RenderCapabilityUnavailable(f"RENDER_CAPABILITY_UNAVAILABLE: {self._reason}")

    def shutdown(self) -> None:
        return None


def select_adapters(run_root: Path, *, launch_command: Sequence[str] = (),
                    allow_hosts: Sequence[str] | None = None) -> dict[str, RenderAdapter]:
    """Every adapter this run could use, keyed by id, with real probes.

    Both are always returned. The unavailable one is in the matrix so a run without a
    browser reports *why* rather than reporting nothing, which is the difference
    between a blocked render and a missing record.
    """
    chromium = ChromiumRenderAdapter(
        run_root=run_root, launch_command=launch_command, allow_hosts=allow_hosts,
    )
    available, reason = chromium.available()
    adapters: dict[str, RenderAdapter] = {
        chromium.id: chromium,
        UnavailableRenderAdapter.id: UnavailableRenderAdapter(reason if not available else ""),
    }
    return adapters


def capability_matrix(adapters: Mapping[str, RenderAdapter]) -> list[dict]:
    return [adapter.capability_record() for adapter in adapters.values()]


def free_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class LocalServer:
    """A static file server on loopback, for capturing a built surface.

    Launched as an argv list with ``shell=False``, bound to 127.0.0.1 only, and torn
    down in :meth:`shutdown` including on the failure paths -- a leaked server holding
    a port is the kind of thing that makes the *next* test fail for no visible reason.
    """

    def __init__(self, directory: Path, *, port: int = 0) -> None:
        self.directory = Path(directory)
        self.port = int(port) or free_port()
        self._process: Any = None

    def start(self) -> str:
        """Start the server and return its URL, once it is genuinely accepting connections.

        Returning immediately after ``Popen`` is a race: the child has been created but
        has not yet bound the socket, so the first navigation hits a port nothing is
        listening on, every capture in the run is refused, and the failure surfaces far
        from its cause as "no validated capture is available to critique". That is
        intermittent by nature -- it depends on how fast the interpreter starts -- which is
        exactly the kind of failure that gets mistaken for flakiness in the tool above.

        So: poll the port until it accepts, and fail loudly if it never does.
        """
        import socket
        import subprocess

        if not self.directory.is_dir():
            raise CaptureFailed(f"CAPTURE_FAILED: the surface to render does not exist: {self.directory}")
        handler = Path(tempfile.gettempdir()) / f"ariadne-serve-{self.port}.py"
        handler.write_text(SERVER_SOURCE, encoding="utf-8")
        argv = safety.safe_launch_command(
            ["python", str(handler), str(self.directory), str(self.port)], working_root=self.directory,
        )
        self._process = subprocess.Popen(
            argv, cwd=str(self.directory), stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, shell=False,
        )
        deadline = time.monotonic() + SERVER_READY_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise CaptureFailed(
                    f"CAPTURE_FAILED: the surface server exited immediately with code "
                    f"{self._process.returncode}; nothing can be captured from a surface that is "
                    "not running"
                )
            with socket.socket() as probe:
                probe.settimeout(0.25)
                if probe.connect_ex(("127.0.0.1", self.port)) == 0:
                    return f"http://127.0.0.1:{self.port}/"
            time.sleep(SERVER_POLL_SECONDS)
        self.shutdown()
        raise CaptureFailed(
            f"CAPTURE_FAILED: the surface server did not begin listening on port {self.port} "
            f"within {SERVER_READY_TIMEOUT_SECONDS}s; capturing from a surface that may not be up "
            "would produce blank images that look like evidence"
        )

    def is_serving(self, *, timeout: float = 0.25) -> bool:
        """Whether the port is accepting a connection right now.

        Lives here rather than in the suite because the suite is release tooling, and
        release tooling is held to "no network imports outside the launcher". Loopback is
        not a network dependency, but a test that reached for ``socket`` to prove the
        server was up would be one the offline guard rightly flags, and the honest fix is
        to ask the component that owns the socket rather than to import one of its own.
        """
        import socket

        if self._process is None:
            return False
        with socket.socket() as probe:
            probe.settimeout(float(timeout))
            return probe.connect_ex(("127.0.0.1", self.port)) == 0

    def shutdown(self) -> None:
        if self._process is None:
            return
        try:
            self._process.terminate()
            self._process.wait(timeout=10)
        except Exception:  # noqa: BLE001 - a stubborn child is killed, not leaked
            try:
                self._process.kill()
                self._process.wait(timeout=5)
            except Exception:  # noqa: BLE001
                pass
        finally:
            self._process = None


SERVER_SOURCE = '''"""Static file server for a rendered capture. Loopback only."""
import http.server
import socketserver
import sys
import os

ROOT, PORT = sys.argv[1], int(sys.argv[2])


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


class Server(socketserver.TCPServer):
    allow_reuse_address = True


with Server(("127.0.0.1", PORT), Handler) as httpd:
    os.chdir(ROOT)
    httpd.serve_forever()
'''


__all__ = [
    "RenderCapabilityUnavailable",
    "CaptureFailed",
    "ProbeResult",
    "CaptureResult",
    "RenderAdapter",
    "ChromiumRenderAdapter",
    "UnavailableRenderAdapter",
    "LocalServer",
    "probe_playwright",
    "select_adapters",
    "capability_matrix",
    "free_port",
    "INSPECT_SCRIPT",
    "LOADING_SELECTORS",
    "ERROR_TEXT_MARKERS",
    "EMPTY_BODY_THRESHOLD",
]
