"""Ariadne executable orchestration core (AR-201).

The engine owns the parts of Ariadne that must not depend on an agent's
goodwill: versioned records, the state transition choke point, gate
authorization, continuation preconditions and review binding. The existing
runtime (`scripts/ariadne.py`) and transport (`scripts/prepare-stage.py`) keep
their behaviour and delegate protected operations to this package.

Design rules for the whole package:

* standard library only; no new runtime dependency;
* pure contracts where possible (no implicit file writes on read);
* every refusal carries a human-readable reason and changes no state;
* nothing here proves a human typed a command. Approval channels are
  authorization bookkeeping, not process isolation.
"""

from __future__ import annotations

from importlib import metadata
from pathlib import Path


def package_version() -> str:
    """Return installed metadata, or the source-tree VERSION during development."""
    try:
        return metadata.version("ariadne")
    except metadata.PackageNotFoundError:
        source_version = Path(__file__).resolve().parents[2] / "VERSION"
        return source_version.read_text(encoding="utf-8").strip() if source_version.is_file() else "unknown"


__version__ = package_version()

from . import (  # noqa: E402
    api,
    artifacts,
    capabilities,
    components,
    context,
    contracts,
    critique,
    decisions,
    design,
    economics,
    efficiency,
    events,
    execution,
    harness,
    history,
    integration,
    migration,
    orchestration,
    persistence,
    policy,
    prompting,
    provenance,
    public,
    recovery,
    references,
    release,
    render,
    review,
    routing,
    serialization,
    statemachine,
    tooling,
    verification,
)

__all__ = [
    "__version__",
    "package_version",
    "api",
    "artifacts",
    "capabilities",
    "components",
    "context",
    "contracts",
    "critique",
    "decisions",
    "design",
    "economics",
    "efficiency",
    "events",
    "execution",
    "harness",
    "history",
    "integration",
    "migration",
    "orchestration",
    "persistence",
    "policy",
    "prompting",
    "provenance",
    "public",
    "recovery",
    "references",
    "release",
    "render",
    "review",
    "routing",
    "serialization",
    "statemachine",
    "tooling",
    "verification",
]
