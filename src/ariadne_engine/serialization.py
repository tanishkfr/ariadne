"""Deterministic serialization, stable prefixes and the memo cache (AR-204 T3/T12).

Why this module exists
----------------------
A reusable prompt prefix is only reusable if the same logical content renders the
same bytes twice. Python's default ``json.dumps`` ordering (insertion order) and
its default separators make that easy to get wrong: two equivalent mappings can
render differently, and a re-ordered tool list silently changes the prefix and
therefore the provider cache digest.

This module provides the four deterministic primitives the harness uses:

* :func:`canonical_json` / :func:`canonical_bytes` - one byte string for one
  logical value, whatever order the caller built it in;
* :func:`stable_digest` - a digest over labelled parts, so a digest can name what
  it covers;
* :func:`stable_prefix` - an ordered segment plan with explicit cache boundaries,
  so "what is cacheable" is a recorded structural fact rather than a guess;
* :class:`Memo` - a process-local memo cache whose entries are *bytes or digests
  only*. A memo can make a repeated deterministic computation cheaper; it can
  never authorize, verify or satisfy evidence. That rule is what keeps a stale
  cache from becoming a stale approval.

Nothing here calls a provider, reads the network or writes files. Byte identity
is testable offline, which is exactly the property a cache prefix needs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

STABLE = "stable"
VOLATILE = "volatile"
CACHE_BOUNDARY = "cache-boundary"

SEGMENT_STABILITIES = (STABLE, VOLATILE)


def canonical_json(value: Any) -> str:
    """One deterministic JSON string for one logical value.

    Object keys are sorted, separators are tight, and floats are rendered with
    ``repr`` (which round-trips) rather than a locale-dependent format. A value
    that JSON cannot represent is refused rather than stringified silently.
    """
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"value is not canonically serialisable: {exc}") from exc


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_text(text: str) -> str:
    return digest_bytes(text.encode("utf-8"))


def stable_digest(*parts: Any) -> str:
    """A digest over labelled parts.

    Each part is rendered canonically and separated by a NUL byte, so
    ``stable_digest("ab", "c")`` and ``stable_digest("a", "bc")`` cannot collide.
    """
    rendered = "\0".join(canonical_json(part) for part in parts)
    return digest_text(rendered)


def deep_sorted(value: Any) -> Any:
    """A recursively key-sorted copy. Lists keep their order (order is data)."""
    if isinstance(value, Mapping):
        return {str(key): deep_sorted(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [deep_sorted(item) for item in value]
    return value


def normalise_text(text: str) -> str:
    """The canonical text form used for hashing: LF line endings, no trailing space.

    This is a *hashing* normalisation. It is never applied to delivered content:
    the packet delivers the original bytes, and this only makes two texts that
    differ solely by line ending or trailing whitespace compare equal for cache
    purposes. Trailing blank lines are dropped because a cache key should not
    change because a file ended with one more newline.
    """
    lines = [line.rstrip() for line in str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).rstrip("\n")


def stable_rows(rows: Iterable[Mapping], *, key: str) -> list[dict]:
    """Rows sorted by one field, ties broken by the canonical form of the row."""
    ordered = list(rows)
    return sorted(ordered, key=lambda row: (str(row.get(key, "")), canonical_json(row)))


# ------------------------------------------------------------- stable prefixes


def segment(
    segment_id: str,
    text: str,
    *,
    stability: str = STABLE,
    cacheable: bool = True,
    role: str = "",
) -> dict:
    """One labelled piece of a request, with its measured size and digest.

    ``stability`` is the claim the *assembly* makes about this segment: a
    ``stable`` segment must render identically for every request that reuses the
    prefix. A segment that carries a run id, packet id, timestamp, revision or
    environment value is ``volatile`` even when it is small.
    """
    if stability not in SEGMENT_STABILITIES:
        raise ValueError(f"unsupported segment stability: {stability!r}")
    text = str(text)
    encoded = text.encode("utf-8")
    return {
        "segment_id": str(segment_id),
        "role": str(role),
        "stability": stability,
        "cacheable": bool(cacheable) and stability == STABLE,
        "bytes": len(encoded),
        "digest": digest_bytes(encoded),
        "text": text,
    }


def stable_prefix(segments: Sequence[Mapping]) -> dict:
    """An ordered prefix plan: stable segments first, then one boundary, then volatile.

    The plan is deterministic: the caller's stable segments keep their order
    (order is part of what the model sees), and the volatile segments keep theirs.
    Reversing two stable segments changes the prefix digest, which is correct:
    the model would see a different prompt.

    The boundary index is the number of stable segments; a provider adapter may
    use it as a cache breakpoint, and a provider without explicit breakpoints
    gets an equivalent stable-first ordering.
    """
    stable: list[dict] = []
    volatile: list[dict] = []
    for item in segments:
        if not isinstance(item, Mapping) or not str(item.get("segment_id", "")):
            raise ValueError("a prefix segment needs an id and a stability")
        if str(item.get("stability", "")) == STABLE:
            stable.append(dict(item))
        elif str(item.get("stability", "")) == VOLATILE:
            volatile.append(dict(item))
        else:
            raise ValueError(f"unsupported segment stability: {item.get('stability')!r}")
    prefix_text = "".join(str(item.get("text", "")) for item in stable)
    volatile_text = "".join(str(item.get("text", "")) for item in volatile)
    prefix_bytes = prefix_text.encode("utf-8")
    return {
        "schema_version": 1,
        "segments": [*stable, *volatile],
        "stable_segments": len(stable),
        "volatile_segments": len(volatile),
        "boundary_index": len(stable),
        "boundary_label": CACHE_BOUNDARY,
        "stable_prefix_bytes": len(prefix_bytes),
        "stable_prefix_digest": digest_bytes(prefix_bytes),
        "volatile_bytes": len(volatile_text.encode("utf-8")),
        "total_bytes": len(prefix_bytes) + len(volatile_text.encode("utf-8")),
        "stable_prefix_text": prefix_text,
        "volatile_text": volatile_text,
    }


def prefix_identity(plan: Mapping, other: Mapping) -> dict:
    """Compare two prefix plans. Used by the byte-identity contract tests."""
    left = str(plan.get("stable_prefix_digest", ""))
    right = str(other.get("stable_prefix_digest", ""))
    left_bytes = str(plan.get("stable_prefix_text", ""))
    right_bytes = str(other.get("stable_prefix_text", ""))
    return {
        "identical": left == right and left_bytes == right_bytes,
        "digest_left": left,
        "digest_right": right,
        "bytes_left": len(left_bytes.encode("utf-8")),
        "bytes_right": len(right_bytes.encode("utf-8")),
    }


# ---------------------------------------------------------------- memo cache


class Memo:
    """A process-local memo with a declared key, dependency and version.

    Every entry records the dependency it was computed under. A read is a hit
    only when the dependency is *exactly* equal; anything else is a miss that
    recomputes. There is no partial invalidation and no TTL, because a
    time-based rule would make "is this still true" depend on the clock.

    A memo value is a byte string, a digest or a small serialisable value used to
    render those. It is never a verification, an approval, a capability status or
    an authorization decision: callers must not route authority through it, and
    the engine's own guards do not consult it.
    """

    VALUE_KINDS = ("bytes", "text", "digest", "value")

    def __init__(self, name: str, *, version: int = 1) -> None:
        if not str(name).strip():
            raise ValueError("a memo needs a name")
        self.name = str(name)
        self.version = int(version)
        self._entries: dict[str, dict] = {}
        self._hits = 0
        self._misses = 0
        self._invalidations = 0

    def _key(self, key: Any) -> str:
        return canonical_json({"k": str(key), "v": self.version})

    def get(self, key: Any, dependency: Any) -> dict | None:
        """Return a hit, or ``None``. A dependency mismatch is a miss and evicts."""
        slot = self._entries.get(self._key(key))
        if slot is None:
            self._misses += 1
            return None
        if canonical_json(deep_sorted(dependency)) != slot["dependency"]:
            self._entries.pop(self._key(key), None)
            self._invalidations += 1
            self._misses += 1
            return None
        self._hits += 1
        return {
            "value": slot["value"],
            "kind": slot["kind"],
            "dependency": json.loads(slot["dependency"]),
            "memo": self.name,
            "version": self.version,
        }

    def put(self, key: Any, dependency: Any, value: Any, *, kind: str = "value") -> dict:
        if kind not in self.VALUE_KINDS:
            raise ValueError(f"unsupported memo value kind: {kind!r}")
        if kind == "value":
            # Round-trip through canonical JSON so a caller cannot store a mutable
            # object and mutate the cached value behind the memo's back.
            value = json.loads(canonical_json(value))
        self._entries[self._key(key)] = {
            "value": value,
            "kind": kind,
            "dependency": canonical_json(deep_sorted(dependency)),
            "stored_at": None,
        }
        return {"memo": self.name, "key": str(key), "kind": kind}

    def invalidate(self, key: Any | None = None) -> int:
        if key is None:
            removed = len(self._entries)
            self._entries.clear()
        else:
            removed = 1 if self._entries.pop(self._key(key), None) is not None else 0
        self._invalidations += removed
        return removed

    def stats(self) -> dict:
        return {
            "memo": self.name,
            "version": self.version,
            "entries": len(self._entries),
            "hits": self._hits,
            "misses": self._misses,
            "invalidations": self._invalidations,
            "note": "a memo accelerates a deterministic computation; it never satisfies evidence",
        }


__all__ = [
    "STABLE",
    "VOLATILE",
    "CACHE_BOUNDARY",
    "SEGMENT_STABILITIES",
    "canonical_json",
    "canonical_bytes",
    "digest_bytes",
    "digest_text",
    "stable_digest",
    "deep_sorted",
    "normalise_text",
    "stable_rows",
    "segment",
    "stable_prefix",
    "prefix_identity",
    "Memo",
]
