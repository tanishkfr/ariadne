"""The Decision Runtime sidecar: a bounded engine behind a one-line protocol.

Run it as ``python sidecar.py --root <runtime directory>``. It reads one JSON
document per line from standard input, answers one per line on standard output, and
never writes anything else to standard output — diagnostics go to standard error so
they cannot corrupt the stream.

The protocol is four methods. That is the entire wire contract:

``status``        what this engine is, which revision it loaded, what it can answer
``decide``        one state, many questions, as one bounded inference
``decide_batch``  many states, many questions, still one call
``warm``          load ahead of the first real question

It deliberately does **not** speak a general API. The value of isolation comes from
the surface being narrow enough that an engine swap cannot change Ariadne's
behaviour; a runtime that needed twenty methods would be an authority, not a
classifier.

Failure is reported, never guessed. An exception becomes an ``error`` reply with the
message, Ariadne records a failed decision and takes its normal fallback. The sidecar
does not exit on a bad request, because one malformed projection must not take the
engine down for the rest of the run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

if __package__ in (None, ""):  # pragma: no cover - only when run as a plain script
    # Launched by path (``python .../sidecar.py --root <dir>``), so there is no package
    # context for a relative import. Prepending the source root makes the absolute
    # fallback below resolvable.
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    # Imported as a package module. The relative form is the only one that works when
    # Ariadne's engine package has been loaded under a different module name, which is
    # exactly what the maintainer test suites do.
    from .reference import ENGINE_NAME, ReferenceBoundedEngine, empty_book, load_weights
    from .transport import WIRE_SCHEMA
except ImportError:  # pragma: no cover - the plain-script launch path
    from ariadne_engine.decisions.runtime.reference import (
        ENGINE_NAME,
        ReferenceBoundedEngine,
        empty_book,
        load_weights,
    )
    from ariadne_engine.decisions.runtime.transport import WIRE_SCHEMA

WEIGHTS_NAME = "weights.json"
"""The weight file a runtime installation ships with."""


def build_engine(root: Path) -> ReferenceBoundedEngine:
    """Load the engine for an installation directory.

    A missing weight file is not an error. It produces an engine that abstains on
    every question with ``NO_LOCAL_MODEL``, which Ariadne escalates — the honest
    behaviour for a runtime with nothing to say.
    """
    weights_path = Path(root) / WEIGHTS_NAME
    if weights_path.is_file():
        return ReferenceBoundedEngine(load_weights(weights_path))
    return ReferenceBoundedEngine(empty_book("no weight file in this installation"))


def handle(request: Mapping[str, Any], engine: ReferenceBoundedEngine) -> Mapping[str, Any]:
    """Dispatch one request. Raises on an unknown method so the caller sees it."""
    if str(request.get("schema", "")) != WIRE_SCHEMA:
        raise ValueError(f"unsupported wire schema {request.get('schema')!r}")
    method = str(request.get("method", ""))
    payload = request.get("payload")
    payload = dict(payload) if isinstance(payload, Mapping) else {}
    if method == "status":
        return engine.status()
    if method == "warm":
        return engine.warm()
    if method == "decide":
        return engine.decide(payload)
    if method == "decide_batch":
        return engine.decide_batch(payload)
    raise ValueError(f"unknown method {method!r}")


def serve(root: Path, stream_in: Any = None, stream_out: Any = None) -> int:
    """Read requests until end of input. Returns a process exit code."""
    source = stream_in if stream_in is not None else sys.stdin
    sink = stream_out if stream_out is not None else sys.stdout
    try:
        engine = build_engine(root)
    except Exception as exc:  # noqa: BLE001 - reported to Ariadne, not swallowed
        print(f"decision runtime failed to load: {exc}", file=sys.stderr, flush=True)
        return 2
    for line in source:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            request = json.loads(stripped)
            if not isinstance(request, Mapping):
                raise ValueError("request is not an object")
            result = handle(request, engine)
            response = {"schema": WIRE_SCHEMA, "result": result}
        except Exception as exc:  # noqa: BLE001 - one bad request must not end the session
            response = {"schema": WIRE_SCHEMA, "error": f"{type(exc).__name__}: {exc}"}
        sink.write(json.dumps(response, sort_keys=True, default=str) + "\n")
        sink.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ariadne Decision Runtime sidecar")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent), help="runtime installation directory")
    parser.add_argument("--describe", action="store_true", help="print the engine status and exit")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if args.describe:
        try:
            print(json.dumps(build_engine(root).status(), indent=2, sort_keys=True, default=str))
        except Exception as exc:  # noqa: BLE001
            print(f"{ENGINE_NAME}: {exc}", file=sys.stderr)
            return 2
        return 0
    return serve(root)


if __name__ == "__main__":
    raise SystemExit(main())