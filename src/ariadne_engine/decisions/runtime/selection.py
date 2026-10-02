"""Provider selection: Ariadne chooses its own bounded implementation.

There is no provider picker, and adding one would be the wrong move in both
directions. A picker makes a technical decision into a user decision, and it makes
Ariadne's intelligence quality depend on a user knowing which of several bounded
engines to name. The product promise is that Ariadne chooses the right form of
intelligence automatically; a picker contradicts it.

So :func:`select_bounded_provider` takes the *existing* provider a caller was going
to use and returns either that provider unchanged or a native bounded one, based on
capability and on whether the slice has been promoted.

The precedence is deliberate:

1. If the caller already passed a working provider, it is used. A caller that has
   explicitly configured something keeps it. AR-205D behaviour is preserved exactly.
2. Otherwise, if the Decision Runtime is available *and* its slice for this decision
   definition is ``ACTIVE`` within its scope, the runtime is authoritative.
3. Otherwise the runtime is wrapped as a *shadow* observer and the provider returned is
   the honest ``UnavailableProvider``, so the existing 2.0 fallback runs unchanged and
   the runtime's prediction is recorded as evidence.

Step 3 is what makes step 2 safe to reach eventually: every promotion is preceded by
however many shadow observations it took to gather, with the authoritative path
untouched the whole time.
"""

from __future__ import annotations

import weakref
from typing import Any, Mapping, Sequence

from ..providers import DecisionProvider, UnavailableProvider
from . import observe, promotion
from .provider import LocalBoundedProvider
from .session import DecisionRuntime

SELECTION_VERSION = "ar-206-selection-1"
"""The selection result shape."""

MODE_AUTHORITATIVE = "AUTHORITATIVE"
"""The runtime's answer is the recorded decision for this slice."""

MODE_SHADOW = "SHADOW"
"""The runtime predicts; the authoritative path is unaffected."""

MODE_FALLBACK = "FALLBACK"
"""No runtime, or the slice is not promoted. The 2.0 safe path runs unchanged."""

_OPEN_SELECTED_SESSIONS: "weakref.WeakSet[DecisionRuntime]" = weakref.WeakSet()


class SelectedSession:
    """The session a selection handed back, with its ownership made explicit.

    Returning a live subprocess with no instruction to close it is a trap: a diagnostic
    that forgets leaves one sidecar process behind on every call, and a few hundred calls
    later the machine is short of process slots. So the returned object says who owns it
    and releases it on ``__exit__``::

        selection = select_bounded_provider(state)
        with selection["runtime"] as session:
            ...  # use selection["provider"]

    A session the caller supplied is *borrowed*: releasing this holder leaves it open,
    because the caller is still using it. One discovered here is *owned* and must be
    released. An explicit ``close()`` on a borrowed session raises rather than quietly
    closing something the caller still holds.
    """

    def __init__(self, session: DecisionRuntime, owned: bool) -> None:
        self._session = session
        self._owned = bool(owned)
        if self._owned:
            _OPEN_SELECTED_SESSIONS.add(session)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)

    @property
    def owned(self) -> bool:
        """Whether releasing this holder also closes the session."""
        return self._owned

    def close(self) -> None:
        if not self._owned:
            raise RuntimeError(
                "this Decision Runtime session was supplied by the caller and is not ours to close"
            )
        _OPEN_SELECTED_SESSIONS.discard(self._session)
        self._session.shutdown()

    def __enter__(self) -> "SelectedSession":
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._owned:
            self.close()

    def __repr__(self) -> str:
        return f"<SelectedSession {'owned' if self._owned else 'borrowed'} {self._session!r}>"


def open_selected_sessions() -> int:
    """How many selected sessions have been handed out and not released.

    A number a diagnostic can report, and a test can assert returns to zero. A resource
    that leaks is only a problem if something can see that it leaked.
    """
    return len(_OPEN_SELECTED_SESSIONS)


def select_bounded_provider(
    state: Mapping[str, Any] | None,
    *,
    provider: DecisionProvider | None = None,
    runtime: DecisionRuntime | None = None,
    definition: str = "",
    question_version: str = "",
    question: Mapping[str, Any] | None = None,
    consequence: str = "LOW",
    scope: Mapping[str, Any] | None = None,
    reversible: bool = True,
    verification_available: bool = False,
    languages: Sequence[str] = ("en",),
) -> dict:
    """Decide which bounded implementation runs, and in which role.

    Returns ``{"mode", "provider", "runtime", "problems", "reasons", "slice"}``.
    ``provider`` is always a usable
    :class:`~ariadne_engine.decisions.providers.DecisionProvider`, so a caller never
    has to branch on ``None``.
    """
    reasons: list[str] = []

    if provider is not None:
        available, reason = provider.available()
        if available:
            return {
                "version": SELECTION_VERSION,
                "mode": MODE_AUTHORITATIVE,
                "provider": provider,
                "runtime": runtime,
                "slice": None,
                "problems": [],
                "reasons": ["an explicitly configured provider is already available and is used unchanged"],
            }
        reasons.append(f"the supplied provider is unavailable: {reason}")

    session = runtime if runtime is not None else DecisionRuntime.discover()
    # Whether this function owns the session decides who has to close it. A discovered
    # subprocess is ours and has to be released; a session the caller passed in is
    # theirs, and shutting it down would break the caller mid-flight.
    owned = runtime is None
    status = session.status()
    if not status["available"]:
        session.shutdown()
        return {
            "version": SELECTION_VERSION,
            "mode": MODE_FALLBACK,
            "provider": provider if provider is not None else UnavailableProvider(),
            "runtime": None,
            "slice": None,
            "problems": list(session.problems()),
            "reasons": reasons + [str(status["detail"])],
        }

    local = LocalBoundedProvider(session)
    available, reason = local.available()
    if not available:
        session.shutdown()
        return {
            "version": SELECTION_VERSION,
            "mode": MODE_FALLBACK,
            "provider": provider if provider is not None else UnavailableProvider(),
            "runtime": None,
            "slice": None,
            "problems": [reason],
            "reasons": reasons + [f"the decision runtime cannot serve as a provider: {reason}"],
        }

    if not definition or not question_version:
        # Without a decision identity a slice cannot be looked up, so the runtime
        # cannot be authoritative. Shadow is still safe and still useful.
        return {
            "version": SELECTION_VERSION,
            "mode": MODE_SHADOW,
            "provider": provider if provider is not None else UnavailableProvider(),
            "runtime": SelectedSession(session, owned),
            "slice": None,
            "problems": [],
            "reasons": [
                "no decision definition or question version was supplied, so no promotion scope can "
                "be checked; the runtime observes in shadow"
            ],
        }

    active = promotion.active_slice(
        state or {},
        decision_definition=definition,
        question_version=question_version,
        model_revision=local.model_version,
    )
    if active is None:
        return {
            "version": SELECTION_VERSION,
            "mode": MODE_SHADOW,
            "provider": provider if provider is not None else UnavailableProvider(),
            "runtime": SelectedSession(session, owned),
            "slice": None,
            "problems": [],
            "reasons": [
                "no adoption slice is ACTIVE for this decision definition, question version and "
                "model revision; the runtime observes in shadow"
            ],
        }

    requested = dict(scope or {}) or {
        "risk": str(consequence),
        "reversible": bool(reversible),
        "verification_available": bool(verification_available),
        "languages": list(languages),
    }
    scope_problems = promotion.scope_matches(active, requested)
    if scope_problems:
        return {
            "version": SELECTION_VERSION,
            "mode": MODE_SHADOW,
            "provider": provider if provider is not None else UnavailableProvider(),
            "runtime": SelectedSession(session, owned),
            "slice": dict(active),
            "problems": list(scope_problems),
            "reasons": [
                "the ACTIVE slice does not cover this use, so the runtime stays in shadow: "
                + "; ".join(scope_problems)
            ],
        }

    return {
        "version": SELECTION_VERSION,
        "mode": MODE_AUTHORITATIVE,
        "provider": local,
        "runtime": session,
        "slice": dict(active),
        "problems": [],
        "reasons": [
            f"the adoption slice {active.get('slice_id')} is ACTIVE for {definition} "
            f"v{question_version} at revision {local.model_version} and covers this scope"
        ],
    }


def observe_if_shadow(
    state: dict,
    selection: Mapping[str, Any],
    *,
    question: Mapping[str, Any],
    projection: Mapping[str, Any],
    authoritative_answer: str,
    authoritative_decision_id: str = "",
    task_id: str = "",
    definition: str = "",
    ground_truth: str = "",
) -> dict:
    """Shadow-observe when the selection says shadow, otherwise do nothing.

    Returns ``{"observed": bool, ...}``. Doing nothing in ``AUTHORITATIVE`` and
    ``FALLBACK`` modes is the point: a runtime that only ever runs in shadow is not
    influencing anything, and a runtime that is authoritative does not also need to
    watch itself.
    """
    if str(selection.get("mode", "")) != MODE_SHADOW:
        return {"observed": False, "reason": f"selection mode is {selection.get('mode')}, not shadow"}
    runtime = selection.get("runtime")
    if runtime is None:
        return {"observed": False, "reason": "no runtime was attached to the shadow selection"}
    return observe.observe(
        state,
        runtime,
        question=question,
        projection=projection,
        authoritative_answer=authoritative_answer,
        authoritative_decision_id=authoritative_decision_id,
        task_id=task_id,
        definition=definition,
        ground_truth=ground_truth,
    )


def describe() -> dict:
    return {
        "version": SELECTION_VERSION,
        "modes": [MODE_AUTHORITATIVE, MODE_SHADOW, MODE_FALLBACK],
        "precedence": [
            "an explicitly configured, available provider is used unchanged",
            "otherwise an ACTIVE adoption slice inside its scope is authoritative",
            "otherwise the runtime observes in shadow and the existing fallback runs",
        ],
        "note": (
            "there is no provider picker: Ariadne owns bounded-implementation selection, and a "
            "promotion is only reachable through recorded shadow evidence"
        ),
    }


def _unused(value: Any) -> Any:  # pragma: no cover
    return observe