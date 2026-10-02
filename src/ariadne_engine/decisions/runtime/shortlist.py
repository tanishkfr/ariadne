"""Shortlisting: shrink a large candidate set before a bounded question is asked.

A bounded classifier is good at a handful of options and poor at hundreds. The reason
is structural rather than a matter of tuning: the answer space is carried in the input,
so every option costs budget, and past a few dozen options each one gets a couple of
tokens. Asking about 400 candidates directly produces a confident answer about a
question that was never really asked.

So large candidate sets are narrowed *first*, and the narrowing is deterministic by
default. That word carries weight: the shortlist prefers a declared, auditable filter
over a similarity score, because a shortlist stage that ranks by embedding similarity
introduces a model into the step that was supposed to remove one.

Three strategies, in preference order:

``declared``
    the candidate carries a declared match key and the state declares what to match.
    Fully deterministic, fully explainable, no runtime call.
``lexical``
    a stable token-overlap score with an explicit tie-break on candidate order. Still
    no model. Chosen over an embedding only because it is reproducible from the
    projection alone.
``embedding``
    only when a caller explicitly supplies an embedding function. Refused rather than
    silently substituted, because the result then depends on a model the projection
    did not name.

Every shortlist is recorded: how many candidates went in, how many survived, which
strategy ran, and what was dropped. A shortlist that silently discards the correct
candidate is otherwise indistinguishable from one that found it.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable, Mapping, Sequence

from ...contracts import ContractError

SHORTLIST_VERSION = "ar-206-shortlist-1"
"""The shortlist record shape."""

DEFAULT_KEEP = 12
"""Candidates kept by default.

Twelve is a bound on the *question*, not a tuning parameter: the runtime's per-option
budget degrades past a few dozen and a 12-option question stays comfortably inside it
for every declared context limit.
"""

MAX_CANDIDATES = 5_000
"""Candidates accepted before the shortlist refuses.

A 5,000-candidate set is almost always a bug upstream — an unbounded enumeration
turned into a decision question — and refusing it surfaces that instead of ranking it.
"""

STRATEGIES = ("declared", "lexical", "embedding")
"""The declared narrowing strategies, in order of preference."""

_TOKEN = re.compile(r"[A-Za-z0-9_]+")


def _tokens(text: Any) -> set[str]:
    return {token for token in _TOKEN.findall(str(text).lower()) if len(token) > 1}


def shortlist(
    candidates: Sequence[Mapping[str, Any]],
    *,
    keep: int = DEFAULT_KEEP,
    strategy: str = "declared",
    match_key: str = "",
    query: str = "",
    embed_fn: Callable[[Sequence[str]], Sequence[Sequence[float]]] | None = None,
) -> dict:
    """Narrow ``candidates`` to at most ``keep`` and record what happened.

    Returns ``{"candidates", "strategy", "kept", "dropped", "total", "digest",
    "passthrough", "note"}``. The record is the point: an unexplained shortlist cannot
    be audited, and an unauditable narrowing step inside a decision path is where
    correctness quietly disappears.
    """
    if strategy not in STRATEGIES:
        raise ContractError(f"unknown shortlist strategy: {strategy!r}; use one of {', '.join(STRATEGIES)}")
    total = len(candidates)
    if total > MAX_CANDIDATES:
        raise ContractError(
            f"{total} candidates exceeds the shortlist bound of {MAX_CANDIDATES}; "
            "an unbounded enumeration is not a decision question"
        )
    if not isinstance(keep, int) or isinstance(keep, bool) or keep < 2:
        raise ContractError(f"a shortlist must keep at least two candidates, got {keep!r}")
    if total <= keep:
        # Nothing to narrow. Recorded as a passthrough so the record distinguishes
        # "we kept everything because there was little" from "we kept everything
        # because the filter did nothing".
        return {
            "version": SHORTLIST_VERSION,
            "strategy": strategy,
            "candidates": [dict(item) for item in candidates],
            "labels": [str(item.get("label", "")) for item in candidates],
            "kept": total,
            "dropped": 0,
            "total": total,
            "passthrough": True,
            "digest": _digest(candidates),
            "note": "the candidate set was already within the bound, so no narrowing ran",
        }
    if strategy == "declared":
        kept, detail = _declared(candidates, keep, match_key, query)
    elif strategy == "lexical":
        kept, detail = _lexical(candidates, keep, query)
    else:
        if embed_fn is None:
            raise ContractError(
                "the embedding shortlist strategy requires an embedding function; Ariadne will not "
                "substitute a different strategy silently"
            )
        kept, detail = _embedding(candidates, keep, query, embed_fn)
    return {
        "version": SHORTLIST_VERSION,
        "strategy": strategy,
        "candidates": kept,
        "labels": [str(item.get("label", "")) for item in kept],
        "kept": len(kept),
        "dropped": total - len(kept),
        "total": total,
        "passthrough": False,
        "digest": _digest(candidates),
        "detail": detail,
        "note": "narrowing happened before the bounded question; the dropped candidates are recorded",
    }


def _declared(
    candidates: Sequence[Mapping[str, Any]],
    keep: int,
    match_key: str,
    query: str,
) -> tuple[list[dict], dict]:
    """Candidates whose declared match key contains the query, in declared order.

    Deterministic and explainable: the surviving set is exactly the candidates whose
    declared key matches, and their order is the caller's order.
    """
    if not str(match_key or "").strip():
        raise ContractError(
            "the declared shortlist strategy needs a match_key naming the candidate field to compare"
        )
    needle = str(query or "").strip().lower()
    if not needle:
        raise ContractError("the declared shortlist strategy needs a query to match against")
    kept = [
        dict(item)
        for item in candidates
        if needle in str(item.get(match_key, "")).lower()
    ]
    if len(kept) < 2:
        # Too few survived to form a question. Fall back to the declared order rather
        # than inventing a ranking, and say so.
        kept = [dict(item) for item in candidates][:keep]
        return kept, {"reason": "fewer than two candidates matched; kept the first in declared order"}
    return kept[:keep], {"match_key": str(match_key), "matched": len(kept), "reason": "declared match on a named field"}


def _lexical(
    candidates: Sequence[Mapping[str, Any]],
    keep: int,
    query: str,
) -> tuple[list[dict], dict]:
    """Stable token overlap, tie-broken by declared order.

    ``mergesort`` rather than the default sort so equal scores keep their declared
    order, which is what makes this reproducible: the same projection and the same
    candidate list always produce the same shortlist.
    """
    query_tokens = _tokens(query)
    scored: list[tuple[float, int, dict]] = []
    for position, item in enumerate(candidates):
        candidate_tokens = _tokens(item.get("label", "")) | _tokens(item.get("text", ""))
        if not candidate_tokens or not query_tokens:
            overlap = 0.0
        else:
            overlap = len(query_tokens & candidate_tokens) / len(query_tokens | candidate_tokens)
        scored.append((-round(overlap, 8), position, dict(item)))
    scored.sort(key=lambda row: (row[0], row[1]))
    kept = [row[2] for row in scored[:keep]]
    return kept, {"reason": "token overlap with declared-order tie-break; no model was involved"}


def _embedding(
    candidates: Sequence[Mapping[str, Any]],
    keep: int,
    query: str,
    embed_fn: Callable[[Sequence[str]], Sequence[Sequence[float]]],
) -> tuple[list[dict], dict]:
    """Cosine over caller-supplied embeddings, used only when explicitly requested."""
    texts = [f"{query}\n{str(item.get('label', ''))} {str(item.get('text', ''))}".strip() for item in candidates]
    vectors = list(embed_fn(texts))
    if len(vectors) != len(candidates):
        raise ContractError("the embedding function returned a different number of vectors than candidates")
    scored: list[tuple[float, int, dict]] = []
    base = _unit(vectors[0])
    for position, (item, vector) in enumerate(zip(candidates, vectors)):
        similarity = sum(a * b for a, b in zip(base, _unit(vector)))
        scored.append((-round(similarity, 8), position, dict(item)))
    scored.sort(key=lambda row: (row[0], row[1]))
    kept = [row[2] for row in scored[:keep]]
    return kept, {"reason": "cosine over a caller-supplied embedding function; the model is not Ariadne's"}


def _unit(vector: Sequence[float]) -> list[float]:
    magnitude = sum(float(value) ** 2 for value in vector) ** 0.5
    if magnitude == 0:
        return [0.0 for _ in vector]
    return [float(value) / magnitude for value in vector]


def _digest(candidates: Sequence[Mapping[str, Any]]) -> str:
    canonical = json.dumps(
        [dict(item) for item in candidates], sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def describe() -> dict:
    return {
        "version": SHORTLIST_VERSION,
        "strategies": list(STRATEGIES),
        "default_keep": DEFAULT_KEEP,
        "max_candidates": MAX_CANDIDATES,
        "note": (
            "the declared and lexical strategies are model-free and reproducible; the embedding "
            "strategy is refused unless a caller supplies the embedding function explicitly"
        ),
    }