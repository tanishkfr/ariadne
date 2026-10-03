"""Grounded Design Intelligence: AR-220's reference/evidence substrate.

This package answers one question in an auditable way:

> **Why did you choose this design?**

with:

> Because these inspected references support these specific principles, this
> project already establishes these constraints, and this direction synthesises
> them without copying any single source.

Five permanent rules, each enforced in code rather than asserted in prose:

> **References are evidence, not authority.**
> **Observed is not recommended. Recommended is not approved.**
> **MCP and CLI are transports, not trust.**
> **getdesign.md is a useful curated source, not ground truth.**
> **Project identity comes before external inspiration.**

The module map:

===================  ===========================================================
:mod:`safety`        SSRF, containment, prompt-injection scanning, resource bounds
:mod:`designmd`      DESIGN.md as an *input format* (bounded YAML subset)
:mod:`normalize`     raw bytes -> one provider-neutral ``DesignReference``
:mod:`getdesign`     the getdesign.md adapter (the only site-aware module)
:mod:`discovery`     project-local evidence, examined before anything external
:mod:`sets`          ``ReferenceSet``: roles, counter-references, diversity, budget
:mod:`transports`    MCP and CLI boundaries that are transports, not trust
:mod:`direction`     the grounded design-direction compiler
:mod:`acquire`       search -> candidate -> fetch -> normalize -> register
===================  ===========================================================

AR-220 stops at approved-ready direction evidence. It performs no UI
implementation, no rendered capture and no reference-aware critique; that is
AR-221's scope.
"""

from __future__ import annotations

from pathlib import Path

from .. import contracts  # noqa: F401  (re-exported for callers of this package)
from . import (  # noqa: E402
    acquire,
    designmd,
    direction,
    discovery,
    getdesign,
    normalize,
    safety,
    sets,
    transports,
)

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "getdesign-md"
"""The frozen getdesign.md corpus used by every regression test.

These bytes were retrieved once from the maintainers' public MIT-licensed
repository and recorded verbatim, with their provenance in ``retrieval.json``.
No unit or regression test touches the network.
"""


def capability_matrix(*, include_fixtures: bool = True) -> dict:
    """Every reference transport this build declares, and its honest availability.

    Nothing here is required for Ariadne to design. The matrix exists so a run can
    state what it *could* have consulted, which is a different and more useful
    fact than silently having no vocabulary for the question.
    """
    adapters: list[object] = [getdesign.default_adapter(FIXTURE_ROOT if include_fixtures else None)]
    adapters.extend(transports.default_mcp_adapters())
    adapters.extend(transports.default_cli_adapters())
    records = [adapter.capability_record() for adapter in adapters if hasattr(adapter, "capability_record")]
    return {
        "transports": records,
        "mcp": transports.transport_view(transports.default_mcp_adapters()),
        "cli": transports.transport_view(transports.default_cli_adapters()),
        "getdesign": getdesign.default_adapter(FIXTURE_ROOT if include_fixtures else None).capability_record(),
        "required_for_core": False,
        "note": (
            "a disabled transport is a valid transport: it reports its own reason and every retrieval "
            "through it becomes a recorded unavailable capability rather than an exception"
        ),
    }


def external_capability_state() -> dict:
    """Whether external reference acquisition is available at all.

    ``UNAVAILABLE`` is a first-class answer, not an error. When it holds, the
    design workflow continues from project-local evidence if that is sufficient.
    """
    adapter = getdesign.default_adapter(FIXTURE_ROOT)
    if adapter.enabled():
        return {
            "external_reference_capability": "AVAILABLE",
            "reason": "",
            "mode": "offline-fixture",
            "sources": [adapter.id],
        }
    return {
        "external_reference_capability": "UNAVAILABLE",
        "reason": adapter.unavailable_reason(),
        "mode": "none",
        "sources": [],
        "note": (
            "Ariadne does not require external reference acquisition to design. Project-local evidence "
            "continues to work, and the absence of a network source is recorded rather than concealed"
        ),
    }


__all__ = [
    "FIXTURE_ROOT",
    "acquire",
    "capability_matrix",
    "contracts",
    "designmd",
    "direction",
    "discovery",
    "external_capability_state",
    "getdesign",
    "normalize",
    "safety",
    "sets",
    "transports",
]