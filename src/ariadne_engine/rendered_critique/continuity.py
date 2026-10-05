"""Critic continuity across repair rounds, without giving up independence (AR-222D).

AR-222 established that the reviewer is independent: a whitelist packet, withheld
implementation rationale, and a refusal to let the implementer be the reviewer. That is
correct and it has a cost the milestone did not address.

The cost is **round-to-round amnesia**:

```text
round 1  critic: the 390px table clips `method` and `path`
         repair:  the worker does something bounded
round 2  a fresh critic with no memory: the type scale is inconsistent
         repair:  the worker changes the type scale
round 3  a fresh critic again: the density feels off
```

Nothing here is a rule violation. Each round is independently valid, each critique is
independently honest, and the loop wanders because the critic's *taste* is re-rolled every
time. Worse, a repair that half-fixed round 1's finding gets re-litigated from scratch,
because the new critic has no idea a repair was already attempted.

So :func:`session` gives a review round a ``review_session_id`` and a memory of:

* what was previously reported,
* what repair was requested,
* what was previously **declined, and why**,
* the before-captures.

And the independence boundary is unchanged, which is the whole difficulty:

> **Continuity must not become familiarity.**

The memory carries *findings, requests and reasons*. It never carries the implementer's
rationale. Round 2's reviewer knows what round 1 asked for and can check whether it landed;
it does not know how the worker justified its approach, and must not.

:func:`memory_problems` enforces that by refusing a session whose memory grew an
implementation-rationale field -- the same class of leak AR-222's whitelist already
refuses, re-checked here where continuity introduces a new path for it to travel.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .. import contracts
from ..contracts import ContractError

MEMORY_FORBIDDEN_FIELDS = (
    "implementation_rationale",
    "repair_rationale",
    "worker_self_assessment",
    "worker_note",
    "how_i_did_it",
    "approach",
    "implementation_notes",
    "diff",
    "patch",
    "changed_lines",
)
"""Fields a critic's memory may never carry.

The AR-222 whitelist protects the *first* packet. Continuity creates a second channel --
round 2's packet -- and a second channel is a second opportunity to leak. Rather than
trust the caller to remember, every field name that could carry the worker's reasoning is
refused outright when the session is built.
"""

MEMORY_ALLOWED_FIELDS = (
    "previous_findings",
    "requested_repairs",
    "declined_requests",
    "before_capture_ids",
    "repair_attempts",
    "prior_requirement_ids",
)
"""Exactly what continuity is allowed to remember.

Everything here is either an observation the critic made itself, a repair it asked for, or
a reason a repair was declined. Nothing here tells it what the worker was thinking.
"""

DECLINE_REASONS = (
    "violates project identity",
    "reintroduces a deliberately avoided default",
    "contradicts an approved direction",
    "undoes its own prior requirement without evidence",
    "breaks accessibility",
    "exceeds approved scope",
    "requires direction revision",
)
"""Why the system may refuse a critic recommendation.

Copied from the interruption policy deliberately rather than imported: the refinement
loop lives in a different package, and a reviewer that reads the canonical list cannot
quietly disagree with the policy about what counts as a valid reason.
"""

CONTINUITY_MODES = ("CONTINUOUS", "RESTARTED")
"""Whether this round continues the previous one.

``RESTARTED`` is a legitimate answer -- a second reviewer is sometimes the right move --
but it must be *recorded*, because a silent mid-loop change of reviewer is how a loop
starts re-litigating settled questions while looking like progress.
"""


_REASON_STOPWORDS = frozenset({"a", "an", "the", "its", "it", "of", "with", "without", "by", "to"})


def _reason_matches(canonical: str, stated: str) -> bool:
    """Whether a stated decline reason matches one canonical reason.

    Word-boundary matched, and with the stopwords removed. An earlier version tested
    ``token in stated`` over the first two words of each reason, which meant the reason
    *"reintroduces a deliberately avoided default"* matched the free-text string
    *"exceeds approved scope"* -- because its second word is ``"a"`` and ``"a"`` occurs
    inside ``"approved"``. A decline recorded against the wrong canonical reason is worse
    than a decline recorded against none, because the reason is what the next round reads.
    """
    import re

    tokens = [
        word for word in str(canonical).lower().split()
        if word not in _REASON_STOPWORDS
    ]
    if not tokens:
        return False
    head = tokens[0]
    if not re.search(rf"\b{re.escape(head)}", stated):
        return False
    return any(re.search(rf"\b{re.escape(token)}", stated) for token in tokens[1:])


def new_session(*, direction_id: str, task_id: str, reviewer_execution: str,
                reviewer_identity: str = "") -> dict:
    """Open a review session for one direction under one reviewer."""
    if not str(direction_id).strip():
        raise ContractError("a review session is bound to one direction")
    if not str(reviewer_execution).strip():
        raise ContractError(
            "a review session records the reviewer execution. An unidentifiable reviewer cannot "
            "be given continuity or checked for independence"
        )
    return {
        "review_session_id": contracts.new_record_id("rvs"),
        "direction_id": str(direction_id),
        "direction_revision": "",
        "task_id": str(task_id),
        "reviewer_identity": str(reviewer_identity).strip(),
        "reviewer_execution": str(reviewer_execution),
        "mode": CONTINUITY_MODES[0],
        "round": 1,
        "memory": {
            "previous_findings": [],
            "requested_repairs": [],
            "declined_requests": [],
            "before_capture_ids": [],
            "repair_attempts": [],
            "prior_requirement_ids": [],
        },
        "independence": {
            "implementation_rationale_transported": False,
            "allowed_memory_fields": list(MEMORY_ALLOWED_FIELDS),
            "basis": (
                "continuity carries findings, requests and reasons. It does not carry the worker's "
                "reasoning, because a reviewer who knows how the work was done stops being fresh eyes"
            ),
        },
        "restarted_from": "",
        "restart_reason": "",
    }


def continue_session(session: Mapping, *, round_number: int, previous: Mapping | None = None,
                     before_capture_ids: Sequence[str] = ()) -> dict:
    """The next round of the same session, carrying memory forward.

    ``previous`` is the prior critique record. What is extracted is deliberately narrow:
    what was found, what was asked for, what was declined and why, and the before-captures.
    """
    record = {key: value for key, value in dict(session).items()}
    record["memory"] = {
        name: list((session.get("memory") or {}).get(name) or [])
        for name in MEMORY_ALLOWED_FIELDS
    }
    record["round"] = max(1, int(round_number))
    if previous:
        for finding in (previous.get("findings") or []):
            if not isinstance(finding, Mapping):
                continue
            record["memory"]["previous_findings"].append({
                "finding_id": str(finding.get("finding_id", "")),
                "dimension": str(finding.get("dimension", "")),
                "severity": str(finding.get("severity", "")),
                "observation": str(finding.get("observation", "")),
                "state_before": str(finding.get("state", "")),
            })
            for requirement_id in (finding.get("requirement_ids") or []):
                if str(requirement_id) and str(requirement_id) not in record["memory"]["prior_requirement_ids"]:
                    record["memory"]["prior_requirement_ids"].append(str(requirement_id))
        for name in ("before_evidence_set_id", "evidence_set_id"):
            value = str(previous.get(name, ""))
            if value:
                record["memory"]["before_capture_ids"].append(f"{name}:{value}")
                break
    if before_capture_ids:
        record["memory"]["before_capture_ids"].extend(str(item) for item in before_capture_ids)
    record["independence"]["implementation_rationale_transported"] = False
    problems = memory_problems(record)
    if problems:
        raise ContractError("critic memory is not admissible: " + "; ".join(problems))
    return record


def restart_session(session: Mapping, *, reason: str, reviewer_execution: str = "",
                    reviewer_identity: str = "") -> dict:
    """Change reviewer mid-loop -- recorded, with a reason.

    The reason this is allowed at all: a genuinely stuck loop sometimes needs fresh eyes.
    The reason it must be recorded: a loop that silently changes reviewer each round is
    indistinguishable from a loop that is making progress, and it re-proposes the same
    requests forever.
    """
    if not str(reason).strip():
        raise ContractError(
            "changing the reviewer mid-loop states why. A silent switch looks like progress while "
            "re-litigating settled questions"
        )
    record = new_session(
        direction_id=str(session.get("direction_id", "")),
        task_id=str(session.get("task_id", "")),
        reviewer_execution=str(reviewer_execution or session.get("reviewer_execution", "")),
        reviewer_identity=str(reviewer_identity or session.get("reviewer_identity", "")),
    )
    record["mode"] = CONTINUITY_MODES[1]
    record["restarted_from"] = str(session.get("review_session_id", ""))
    record["restart_reason"] = str(reason)
    record["round"] = max(1, int(session.get("round", 1) or 1))
    return record


def request_repair(session: Mapping, *, finding_id: str, request: str) -> dict:
    """Record what this round asked the worker to change."""
    record = {key: value for key, value in dict(session).items()}
    record["memory"] = {name: list(value) for name, value in (session.get("memory") or {}).items()}
    record["memory"]["requested_repairs"].append({
        "finding_id": str(finding_id),
        "request": str(request),
        "round": int(session.get("round", 1) or 1),
    })
    return record


def decline(session: Mapping, *, finding_id: str, recommendation: str, reason: str,
            detail: str = "") -> dict:
    """Explicitly refuse a critic recommendation, and record why.

    Recording the decline is the entire point. A silently-ignored reviewer request is
    indistinguishable from one that was never made, so round 2 proposes it again with the
    same reasoning, and the loop never terminates for a reason anyone can name.
    """
    reasons = [str(item).strip().lower() for item in DECLINE_REASONS]
    stated = " ".join(str(reason or "").lower().split())
    if not stated:
        raise ContractError(
            "declining a critique recommendation records a reason. Declining silently is the same "
            "as ignoring it, and looks like one"
        )
    matched = [item for item in reasons if _reason_matches(item, stated)]
    if not matched:
        raise ContractError(
            f"the recorded reason {reason!r} matches none of the recognised decline reasons: "
            + ", ".join(DECLINE_REASONS)
            + ". An unrecognised decline reason is either a new reason -- add it -- or a "
              "rationalisation, and the two must not be confused."
        )
    record = {key: value for key, value in dict(session).items()}
    record["memory"] = {name: list(value) for name, value in (session.get("memory") or {}).items()}
    record["memory"]["declined_requests"].append({
        "finding_id": str(finding_id),
        "recommendation": str(recommendation),
        "reason": str(reason),
        "canonical_reason": matched[0],
        "detail": str(detail),
        "round": int(session.get("round", 1) or 1),
    })
    return record


def memory_problems(session: Mapping) -> list[str]:
    """Whether a session's memory is admissible.

    Refuses leaked implementation fields by name, refuses a reviewer swap without a
    reason, and refuses a memory that forgot to carry the prior findings -- the last being
    the failure mode continuity is supposed to prevent.
    """
    problems: list[str] = []
    if not str(session.get("review_session_id", "")).strip():
        problems.append("a review session is identified")
    if not str(session.get("reviewer_execution", "")).strip():
        problems.append("a review session names its reviewer execution")
    if str(session.get("mode", "")) not in CONTINUITY_MODES:
        problems.append(
            f"a review session declares its continuity mode: one of {', '.join(CONTINUITY_MODES)}"
        )
    if str(session.get("mode")) == CONTINUITY_MODES[1] and not str(session.get("restart_reason", "")).strip():
        problems.append(
            "this session restarted with a different reviewer and recorded no reason. A silent "
            "switch mid-loop looks like progress while re-proposing settled questions"
        )
    if not str(session.get("restarted_from", "")).strip() and str(session.get("mode")) == CONTINUITY_MODES[1]:
        problems.append("a restarted session names the session it replaced")
    memory = session.get("memory")
    if not isinstance(memory, Mapping):
        problems.append("a review session carries its memory as a mapping")
        return problems
    for name in MEMORY_ALLOWED_FIELDS:
        if name not in memory:
            problems.append(f"critic memory has no {name}")
    for name in MEMORY_FORBIDDEN_FIELDS:
        if name in memory:
            problems.append(
                f"critic memory carries {name!r}. Continuity is not familiarity: a reviewer who "
                "knows how the work was done is no longer fresh eyes"
            )
    independence = session.get("independence")
    if isinstance(independence, Mapping):
        if independence.get("implementation_rationale_transported") not in (False, None):
            problems.append("critic memory records that implementation rationale was transported")
        allowed = [str(item) for item in (independence.get("allowed_memory_fields") or [])]
        leaked = sorted(set(allowed) & set(MEMORY_FORBIDDEN_FIELDS))
        if leaked:
            problems.append(f"the declared memory whitelist includes {leaked}, which may not be remembered")
    for row in (memory.get("declined_requests") or []):
        if not isinstance(row, Mapping):
            continue
        if not str(row.get("reason", "")).strip():
            problems.append(
                f"finding {row.get('finding_id', '?')} has a declined recommendation with no reason"
            )
        stated = " ".join(str(row.get("reason", "")).lower().split())
        if not any(_reason_matches(item, stated) for item in DECLINE_REASONS):
            problems.append(
                f"finding {row.get('finding_id', '?')} was declined for a reason that matches none "
                "of the recognised decline reasons"
            )
    return list(dict.fromkeys(problems))


def did_prior_request_land(session: Mapping, *, finding_id: str, observed: str = "") -> dict:
    """Round N asking whether round N-1's request actually landed.

    This is the question that amnesia prevents. It is a *question* to the reviewer, never
    a verdict from the engine: whether a repair landed is an observation about a render,
    and only a reviewer who looked at the render may answer it.
    """
    rows = [
        row for row in ((session.get("memory") or {}).get("requested_repairs") or [])
        if isinstance(row, Mapping) and str(row.get("finding_id")) == str(finding_id)
    ]
    if not rows:
        return {
            "asked": False,
            "question": "",
            "reason": "no prior repair was requested for this finding, so there is nothing to follow up",
        }
    latest = rows[-1]
    declined = [
        row for row in ((session.get("memory") or {}).get("declined_requests") or [])
        if isinstance(row, Mapping) and str(row.get("finding_id")) == str(finding_id)
    ]
    return {
        "asked": True,
        "question": (
            f"round {latest.get('round', '?')} asked for: {latest.get('request', '')}. "
            f"Does that hold in this render?{(' Observed: ' + observed) if observed else ''}"
        ),
        "requested_in_round": int(latest.get("round", 0) or 0),
        "declined_before": bool(declined),
        "declined_reason": str(declined[-1].get("canonical_reason", "")) if declined else "",
        "not_a_verdict": (
            "this is a question to the reviewer, not a determination. Only a reviewer who looked at "
            "the render may say whether a repair landed"
        ),
    }


def independence_problems(session: Mapping, *, reviewer_execution: str, implementing_execution: str) -> list[str]:
    """Continuity must not have turned into a shared identity."""
    problems: list[str] = []
    reviewer = str(reviewer_execution or "").strip()
    implementer = str(implementing_execution or "").strip()
    if reviewer and implementer and reviewer == implementer:
        problems.append(
            "the reviewer execution and the implementing execution are the same. Continuity of a "
            "session does not permit the worker to review its own work, and giving it the same "
            "session across rounds makes the self-review easier to hide rather than harder"
        )
    recorded = str(session.get("reviewer_execution", "")).strip()
    if recorded and reviewer and recorded != reviewer:
        problems.append(
            f"this session's reviewer is {recorded!r} but {reviewer!r} is reviewing. Either the "
            "session was not restarted (and the reason recorded) or the wrong session was used"
        )
    return problems


def describe(session: Mapping) -> str:
    memory = session.get("memory") if isinstance(session.get("memory"), Mapping) else {}
    return (
        f"session {session.get('review_session_id', '')} round {session.get('round', '?')} "
        f"[{session.get('mode', '')}] reviewer {session.get('reviewer_identity') or session.get('reviewer_execution', '')}: "
        f"{len(memory.get('previous_findings') or [])} prior finding(s), "
        f"{len(memory.get('requested_repairs') or [])} requested repair(s), "
        f"{len(memory.get('declined_requests') or [])} declined"
    )


__all__ = [
    "CONTINUITY_MODES",
    "DECLINE_REASONS",
    "MEMORY_ALLOWED_FIELDS",
    "MEMORY_FORBIDDEN_FIELDS",
    "continue_session",
    "decline",
    "describe",
    "did_prior_request_land",
    "independence_problems",
    "memory_problems",
    "new_session",
    "request_repair",
    "restart_session",
]
