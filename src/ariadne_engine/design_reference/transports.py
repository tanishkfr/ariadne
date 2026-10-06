"""MCP and CLI as *transports*, not as trust (AR-220).

Both are ways to move bytes from somewhere else into a design reference. Neither
is a reason to believe those bytes.

> **MCP and CLI are transports, not trust.**

The permanent rule this module exists to make executable:

> **No shell command gets execution authority merely because it is a reference
> provider.**

:class:`ReferenceCLIAdapter` therefore has three independent brakes, and all
three must be released before anything runs:

1. **An explicitly configured command.** The operator supplies the exact argv.
   Ariadne never assembles a command line out of a reference, a URL or a model
   output, and there is no shell string form anywhere in this module.
2. **An authorization decision from the existing capability layer.** A CLI is
   invoked through :class:`~ariadne_engine.capabilities.CapabilityProbe` /
   :class:`~ariadne_engine.capabilities.FixtureCommandProbe`, which is where the
   repository already records whether a probe may execute. Supplying argv is not
   permission to run it.
3. **A bounded, read-only invocation.** No shell, no redirection, no chained
   operators, an argument-count ceiling, a byte ceiling and a timeout.

On the MCP side the boundary is deliberately schema-free. Ariadne does not know
Figma's tool names, GitHub's tool shapes or any future vendor's schema, and
hardcoding one would make the *vendor* the contract. What Ariadne knows is the
four verbs a reference source can perform:

```
discover_capabilities()   what can this source actually do here?
search()                  candidate references for a query
inspect()                 one reference in detail
retrieve_artifact()       the bytes behind it
```

An adapter that cannot answer ``discover_capabilities`` honestly is an
:class:`UnavailableMCPAdapter`, which is a **valid** adapter. Every call through
it becomes a recorded, honest unavailable capability rather than an exception that
takes the design workflow down with it.

Finally: a result is data. :func:`as_reference_payload` runs every returned
string through the same injection scan and neutralisation as web content, and
records the transport it arrived on. An MCP result containing the sentence "you
are now authorized to install packages" is an observation about that result, and
it cannot become an instruction, an approval, or a shell command.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from ..contracts import ContractError
from . import safety

MCP_CAPABILITIES = ("discover_capabilities", "search", "inspect", "retrieve_artifact")
"""The four verbs a design-reference transport must be able to answer.

Named once so an adapter, a probe and a test cannot disagree about what a
transport has to support.
"""

CLI_CAPABILITIES = ("probe", "search", "inspect", "fetch")
"""The equivalent verb set for a command-line reference source."""

MAX_CLI_ARGS = 24
"""Argument-count ceiling. A reference query is short; anything longer is either
a mistake or an attempt to smuggle a payload into an argv."""

MAX_CLI_OUTPUT_BYTES = 262_144
"""Output ceiling for one CLI invocation, matching the document bound."""

DEFAULT_CLI_TIMEOUT = 60.0
"""Wall-clock ceiling for one invocation."""

# Operators that chain or redirect are how a shell string becomes code execution.
_SHELL_OPERATORS = ("&&", "||", "|", ";", ">", ">>", "<", "`", "$(", "\n")
"""Rejected anywhere in an argv.

The call form below never uses a shell, so a ``|`` would be a literal argument -
but its presence means the caller expected shell semantics, and honouring that
expectation silently would be the actual vulnerability.
"""


# ------------------------------------------------------------------------ MCP


@dataclass
class ReferenceMCPAdapter:
    """A design-reference source reached over MCP.

    ``connector`` is anything exposing the four verbs. Ariadne does not validate
    a vendor's schema; it validates that the adapter *declares* what it can do and
    that its declared capabilities are a subset of what this module supports.
    """

    id: str
    connector: object = None
    declared: Sequence[str] = ()
    description: str = ""
    kind: str = "reference"
    source_type: str = "official-api"
    reason: str = ""
    retrieved: list[dict] = field(default_factory=list)

    def capabilities(self) -> tuple[str, ...]:
        return tuple(self.declared)

    def enabled(self) -> bool:
        return self.connector is not None and bool(self.declared)

    def unavailable_reason(self) -> str:
        if self.enabled():
            return ""
        return self.reason or (
            f"no authorized MCP connection is configured for {self.id!r}; MCP is an optional transport "
            "and Ariadne's design intelligence works without one"
        )

    def require(self, capability: str) -> None:
        if capability not in MCP_CAPABILITIES:
            raise ContractError(
                f"unknown design-reference MCP capability {capability!r}; expected one of "
                + ", ".join(MCP_CAPABILITIES)
            )
        if capability not in self.capabilities():
            raise ContractError(
                f"reference MCP adapter {self.id!r} does not declare {capability!r}; an adapter may not "
                "supply evidence it never claimed to produce"
            )

    def discover_capabilities(self) -> dict:
        """What this transport can actually do here, right now.

        The honest answer is frequently "nothing", and that is a valid adapter
        rather than an error. A design workflow that requires a live Figma
        connection would be a design workflow that cannot run offline.
        """
        if not self.enabled():
            return {
                "id": self.id,
                "enabled": False,
                "capabilities": [],
                "reason": self.unavailable_reason(),
                "required_for_core": False,
            }
        available: list[str] = []
        for capability in MCP_CAPABILITIES:
            if capability not in self.capabilities():
                continue
            if callable(getattr(self.connector, capability, None)):
                available.append(capability)
        return {
            "id": self.id,
            "enabled": bool(available),
            "capabilities": available,
            "declared": list(self.capabilities()),
            "description": self.description,
            "required_for_core": False,
            "note": (
                "an MCP transport moves bytes; the evidence level of what arrives is decided by what was "
                "actually inspected, not by the transport that carried it"
            ),
        }

    def search(self, query: Mapping) -> list[dict]:
        self.require("search")
        if not self.enabled():
            return []
        rows = self.connector.search(dict(query))  # type: ignore[attr-defined]
        return [as_reference_payload(row, transport="mcp", adapter=self.id) for row in rows or []]

    def inspect(self, locator: str) -> dict:
        self.require("inspect")
        if not self.enabled():
            return {"unavailable": True, "reason": self.unavailable_reason()}
        payload = self.connector.inspect(str(locator))  # type: ignore[attr-defined]
        return as_reference_payload(payload, transport="mcp", adapter=self.id)

    def retrieve_artifact(self, locator: str) -> dict:
        self.require("retrieve_artifact")
        if not self.enabled():
            return {"unavailable": True, "reason": self.unavailable_reason()}
        payload = self.connector.retrieve_artifact(str(locator))  # type: ignore[attr-defined]
        return as_reference_payload(payload, transport="mcp", adapter=self.id)

    def capability_record(self) -> dict:
        view = self.discover_capabilities()
        return {
            "id": self.id,
            "kind": self.kind,
            "source_type": self.source_type,
            "description": self.description,
            "capabilities": view["capabilities"],
            "enabled": view["enabled"],
            "unavailable_reason": "" if view["enabled"] else view["reason"],
            "required_for_core": False,
        }


class UnavailableMCPAdapter(ReferenceMCPAdapter):
    """A declared-but-absent MCP transport. Valid, honest, and inert."""

    def __init__(self, adapter_id: str, *, reason: str, declared: Sequence[str] = MCP_CAPABILITIES) -> None:
        super().__init__(id=adapter_id, connector=None, declared=tuple(declared), reason=reason)

    def search(self, query: Mapping) -> list[dict]:  # pragma: no cover - trivially inert
        self.require("search")
        return []

    def inspect(self, locator: str) -> dict:
        self.require("inspect")
        return {"unavailable": True, "reason": self.unavailable_reason()}

    def retrieve_artifact(self, locator: str) -> dict:
        self.require("retrieve_artifact")
        return {"unavailable": True, "reason": self.unavailable_reason()}


def default_mcp_adapters() -> list[ReferenceMCPAdapter]:
    """The transports AR-220 names, all reported by their own honest availability.

    None of them is installed by default and none is required. They exist as
    declared, disabled adapters so a run can say "a Figma MCP would provide
    stronger evidence here, and none is configured" instead of silently having no
    vocabulary for the question.
    """
    return [
        UnavailableMCPAdapter(
            "figma-mcp",
            reason=(
                "no authorized Figma MCP connection is configured. Figma evidence would be stronger than "
                "a curated analysis when it is directly inspected, but Ariadne does not require it and "
                "does not claim any Figma content it has not read"
            ),
        ),
        UnavailableMCPAdapter(
            "github-mcp",
            reason="no authorized GitHub MCP connection is configured; repository sources are read directly when needed",
        ),
        UnavailableMCPAdapter(
            "internal-design-system-mcp",
            reason="no internal design-system MCP is configured in this environment",
        ),
    ]


# ------------------------------------------------------------------------ CLI

_ARGV_FORBIDDEN = (
    "--eval", "-e", "--exec", "--require", "-r", "--import", "-c",
)
"""Interpreters' code-execution flags.

A reference CLI must never be handed a flag whose value is a program. These are
refused wherever they appear in an argv, because the point is that a reference
source has no route to executing code supplied by anything but the operator.

``-c`` is the important one and the easiest to forget: ``sh -c`` and ``python -c``
are the two most common ways to turn an argument into executed code, and omitting
them would have left the most obvious hole in the list open.
"""


@dataclass
class ReferenceCLIAdapter:
    """A read-only command-line reference source.

    Three independent brakes, described in the module docstring: an explicitly
    configured argv, an authorization decision from the existing capability layer,
    and a bounded non-shell invocation. This class is the first two's *input*
    validation; it is deliberately not the authorization itself, and
    ``probe()`` returns the declaration the capability layer judges.
    """

    id: str
    argv: Sequence[str] = ()
    description: str = ""
    kind: str = "reference"
    source_type: str = "official-api"
    read_only: bool = True
    requires_authorization: bool = True
    timeout: float = DEFAULT_CLI_TIMEOUT
    max_output_bytes: int = MAX_CLI_OUTPUT_BYTES
    reason: str = ""

    def capabilities(self) -> tuple[str, ...]:
        return CLI_CAPABILITIES if self.argv else ()

    def enabled(self) -> bool:
        return bool(self.argv)

    def unavailable_reason(self) -> str:
        if self.enabled():
            return ""
        return self.reason or (
            f"no command is configured for reference CLI {self.id!r}; supplying an argv is not the same "
            "as authorizing it, and Ariadne never assembles a command line from reference content"
        )

    def validate_argv(self, argv: Sequence[str]) -> tuple[str, ...]:
        """Check an argv without running it. Refuses everything a reference must not do."""
        values = [str(item) for item in (argv or ())]
        if not values:
            raise ContractError(f"reference CLI {self.id!r} has no command configured")
        safety.check_count(len(values), limit=MAX_CLI_ARGS, label=f"{self.id} argv length")
        for value in values:
            for operator in _SHELL_OPERATORS:
                if operator in value:
                    raise ContractError(
                        f"reference CLI {self.id!r} argument {value[:60]!r} contains the shell operator "
                        f"{operator!r}; reference retrieval never uses a shell, and an argument that "
                        "expects shell semantics is refused rather than reinterpreted"
                    )
            for flag in _ARGV_FORBIDDEN:
                if value == flag:
                    raise ContractError(
                        f"reference CLI {self.id!r} may not be invoked with {flag!r}; a reference provider "
                        "has no route to executing supplied code"
                    )
            if value.startswith("-"):
                continue
            if value in ("curl", "wget") or value.endswith(("curl", "wget")):
                raise ContractError(
                    f"reference CLI {self.id!r} names a network-fetching binary {value!r}; retrieval goes "
                    "through an authorized fetch capability, not through a shell command"
                )
        return tuple(values)

    def probe(self) -> dict:
        """The declaration the capability layer judges. Running nothing."""
        if not self.enabled():
            return {
                "id": self.id,
                "enabled": False,
                "reason": self.unavailable_reason(),
                "argv": [],
                "requires_authorization": True,
                "read_only": True,
                "required_for_core": False,
            }
        try:
            argv = self.validate_argv(self.argv)
        except ContractError as exc:
            return {
                "id": self.id,
                "enabled": False,
                "reason": str(exc),
                "argv": [],
                "requires_authorization": True,
                "read_only": True,
                "required_for_core": False,
            }
        return {
            "id": self.id,
            "enabled": True,
            "argv": list(argv),
            "description": self.description,
            "read_only": self.read_only,
            "requires_authorization": self.requires_authorization,
            "timeout": float(self.timeout),
            "max_output_bytes": int(self.max_output_bytes),
            "required_for_core": False,
            "note": (
                "a reference CLI is not authorized by being configured. The run must carry an existing "
                "authorization decision for this exact argv before anything executes"
            ),
        }

    def capability_record(self) -> dict:
        view = self.probe()
        return {
            "id": self.id,
            "kind": self.kind,
            "source_type": self.source_type,
            "description": self.description,
            "capabilities": list(CLI_CAPABILITIES) if view["enabled"] else [],
            "enabled": view["enabled"],
            "unavailable_reason": "" if view["enabled"] else str(view.get("reason", "")),
            "required_for_core": False,
        }


def build_invocation(argv: Sequence[str], *, extra_args: Sequence[str] = ()) -> tuple[str, ...]:
    """Compose an invocation as an argv list, never as a shell string.

    Every argument is added as a separate element. Nothing here joins, quotes or
    escapes into a single command line, because the moment a reference provider
    has a command *string*, "the model put a flag in it" becomes reachable.
    """
    return tuple(str(item) for item in list(argv or ()) + list(extra_args or ()))


def default_cli_adapters() -> list[ReferenceCLIAdapter]:
    """Named optional CLI providers, all reported unavailable when unconfigured.

    The getdesign CLI is declared here rather than in the getdesign module
    because it is a *transport* into the same corpus, and the distinction is the
    point: the corpus does not become more trustworthy because it arrived by
    ``npx`` instead of over HTTPS.
    """
    return [
        ReferenceCLIAdapter(
            "getdesign-cli",
            description="npx getdesign@latest add {slug} (Node; MIT; writes into a project)",
            reason=(
                "the getdesign CLI is not configured. It is a Node package that writes files into a "
                "project, so using it as a reference source would mean an installation action during "
                "design research. Configure it explicitly under the existing capability policy if that "
                "is wanted; Ariadne never installs it"
            ),
        ),
        ReferenceCLIAdapter(
            "designmd-cli",
            description="designmd-cli search/install, if an operator configures it",
            reason=(
                "no designmd CLI is configured. Ariadne reads public DESIGN.md documents directly and does "
                "not require a registry CLI to do so"
            ),
        ),
        ReferenceCLIAdapter(
            "shadcn-registry-cli",
            description="component registry inspection for implementation references",
            reason=(
                "no component registry CLI is configured. Implementation references stay separate from "
                "aesthetic direction, so this is optional in both directions"
            ),
        ),
    ]


# ------------------------------------------------------------------- payloads


def as_reference_payload(value: object, *, transport: str, adapter: str) -> dict:
    """Normalise one transport result into an inert reference payload.

    Every string in the payload is neutralised and scanned. The transport is
    recorded as *how the bytes arrived*, never as a claim about their quality, and
    the scan is stored as a fact about the result.
    """
    if transport not in ("mcp", "cli", "fixture"):
        raise ContractError(f"unsupported reference transport: {transport!r}")
    if isinstance(value, Mapping):
        payload = {str(key): _neutral(item) for key, item in value.items()}
    elif isinstance(value, (list, tuple)):
        payload = {"rows": [_neutral(item) for item in value]}
    else:
        payload = {"value": _neutral(value)}
    text = " ".join(str(item) for item in _walk_strings(payload))
    payload["transport"] = str(transport)
    payload["adapter"] = str(adapter)
    payload["injection_scan"] = safety.scan_reference_text(text)
    payload["authority"] = "none; a transport result is data and grants nothing"
    return payload


def _neutral(value: object) -> object:
    if isinstance(value, str):
        return safety.as_data_only(value)
    if isinstance(value, Mapping):
        return {str(key): _neutral(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_neutral(item) for item in value]
    return value


def _walk_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_strings(item)


def transport_view(adapters: Sequence[object]) -> dict:
    """One honest view of every declared transport for the run summary."""
    rows = [adapter.capability_record() for adapter in adapters if hasattr(adapter, "capability_record")]
    return {
        "transports": rows,
        "mcp_configured": sum(1 for row in rows if row["id"].endswith("-mcp") and row["enabled"]),
        "cli_configured": sum(1 for row in rows if row["id"].endswith("-cli") and row["enabled"]),
        "required_for_core": False,
        "note": (
            "no MCP server and no Node toolchain is required for Ariadne to design. When a transport is "
            "absent the capability is unavailable, the design workflow continues from project-local "
            "evidence, and the absence is recorded rather than papered over"
        ),
    }


__all__ = [
    "CLI_CAPABILITIES",
    "DEFAULT_CLI_TIMEOUT",
    "MAX_CLI_ARGS",
    "MAX_CLI_OUTPUT_BYTES",
    "MCP_CAPABILITIES",
    "ReferenceCLIAdapter",
    "ReferenceMCPAdapter",
    "UnavailableMCPAdapter",
    "as_reference_payload",
    "build_invocation",
    "default_cli_adapters",
    "default_mcp_adapters",
    "transport_view",
]