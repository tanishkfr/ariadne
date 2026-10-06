# 05 — MCP and CLI Adapters (AR-220)

> **MCP and CLI are transports, not trust.**

## The boundary

Both are ways to move bytes from somewhere else into a design reference. Neither is
a reason to believe those bytes. This document records the contract each obeys and
what is deliberately *not* implemented.

## MCP

### Four verbs

```text
discover_capabilities()   what can this source actually do, here, right now?
search()                  candidate references for a query
inspect()                 one reference in detail
retrieve_artifact()       the bytes behind it
```

An adapter that cannot answer `discover_capabilities()` honestly is an
`UnavailableMCPAdapter` — which is a **valid adapter**. The honest answer is
frequently "nothing", and a design workflow that required a live Figma connection
would be a design workflow that cannot run offline.

### Schema-free by construction

Ariadne does not know Figma's tool names, GitHub's tool shapes, or any future
vendor's schema, and it does not hardcode one. Hardcoding a vendor's schema makes
the *vendor* the contract: adding a source would mean editing the record layer.

What Ariadne knows is the four verbs. An adapter declares which of them it
supports; a call to an undeclared verb is refused:

```text
reference MCP adapter 'partial' does not declare 'inspect'; an adapter may not
supply evidence it never claimed to produce
```

### What a Figma MCP could later provide

The contract is designed so a Figma MCP can supply `frames`, `components`,
`variants`, `styles`, `variables`/`tokens`, `typography`, `spacing` and
`screenshots`/`previews` without any change to `DesignReference`.

**Ariadne claims no live Figma verification.** No Figma MCP is configured, none was
executed, and no Figma content is asserted anywhere in this codebase. What exists
is the capability record:

```text
figma-mcp: unavailable
  no authorized Figma MCP connection is configured. Figma evidence would be
  stronger than a curated analysis when it is directly inspected, but Ariadne
  does not require it and does not claim any Figma content it has not read.
```

Directly inspected Figma content would be `FIGMA_DOCUMENT` at
`DIRECTLY_INSPECTED` — stronger than a curated analysis about the same design. The
distinction lives in the record, not in a special case in the code.

### Shipped adapters (all declared, all disabled)

| Adapter | Capabilities declared | Status | Reason recorded |
|---------|----------------------|--------|-----------------|
| `figma-mcp` | all four | unavailable | no authorized connection configured |
| `github-mcp` | all four | unavailable | repository sources are read directly when needed |
| `internal-design-system-mcp` | all four | unavailable | none configured in this environment |

## CLI

### Four verbs

```text
probe()     declare the command; run nothing
search()
inspect()
fetch()
```

### Three independent brakes

All three must be released before anything runs. This is the executable form of:

> **No shell command gets execution authority merely because it is a reference
> provider.**

**1. An explicitly configured command.** The operator supplies the exact argv.
Ariadne never assembles a command line out of a reference, a URL or model output,
and `build_invocation` returns an argv *list*. There is no shell-string form
anywhere in the module.

**2. An authorization decision from the existing capability layer.** Supplying an
argv is *not* permission to run it. `probe()` returns a declaration; the run must
carry an authorization decision for that exact argv before anything executes:

```json
{
  "enabled": true,
  "argv": ["designmd-cli", "search"],
  "requires_authorization": true,
  "note": "a reference CLI is not authorized by being configured. The run must carry
           an existing authorization decision for this exact argv before anything executes"
}
```

**3. A bounded, read-only invocation.** Validated before any execution:

| Bound | Value |
|-------|-------|
| Shell operators | `&&`, `\|\|`, `\|`, `;`, `>`, `>>`, `<`, `` ` ``, `$(`, newline — refused anywhere in an argv |
| Code-execution flags | `--eval`, `-e`, `--exec`, `--require`, `-r`, `--import`, `-c` |
| Network-fetching binaries | `curl`, `wget` |
| Argument count | ≤ 24 |
| Output | ≤ 256 KiB |
| Timeout | 60 s default |

> An argument containing a shell operator is refused **even though the invocation
> never uses a shell**, where it would be a literal string. The reason is that its
> presence means the caller *expected* shell semantics; honouring that expectation
> silently would be the actual vulnerability.

> `-c` is the flag most worth naming. `sh -c` and `python -c` are the two most
> common ways to turn an argument into executed code, and omitting them would have
> left the most obvious hole in the list open. This was a real gap found by the
> AR-220 adversarial review, not a hypothetical.

### A rejected argv disables the adapter; it is not sanitised

```json
{
  "enabled": false,
  "argv": [],
  "reason": "reference CLI 'test-cli' argument 'search; rm -rf /' contains the shell
             operator ';'; reference retrieval never uses a shell, and an argument
             that expects shell semantics is refused rather than reinterpreted"
}
```

Cleaning a dangerous argv into a working one would be the worst outcome: it would
run something the operator did not configure and report success.

### Shipped adapters (all declared, all disabled)

| Adapter | Purpose | Why it is not configured |
|---------|---------|--------------------------|
| `getdesign-cli` | `npx getdesign@latest add {slug}` (Node, MIT) | it is a Node package that **writes files into a project**, so using it as a reference source would mean an installation action during design research. Ariadne never installs it. |
| `designmd-cli` | `designmd-cli search` / `install` | Ariadne reads public `DESIGN.md` documents directly and does not require a registry CLI. Documented as an optional provider. |
| `shadcn-registry-cli` | component registry inspection | implementation references stay separate from aesthetic direction, so this is optional in both directions. |

`designmd-cli` and `shadcn registry` were investigated per AR-220 §23/§24. The
component-registry flow is documented and supported conceptually:

```text
need a component
    ↓
inspect the project-local component      → LOCAL_DESIGN_FILE / IMPLEMENTATION_REFERENCE
    ↓
inspect an approved registry             → COMPONENT_REGISTRY / IMPLEMENTATION_REFERENCE
    ↓
record an implementation reference
```

but nothing is required, nothing is installed, and no CLI executes.

## The component ladder

Ariadne's implementation evidence is ranked by *rung*, not by aesthetic appeal:

| Rung | Source | Role |
|------|--------|------|
| 1 | the project's own component library | `IMPLEMENTATION_REFERENCE` |
| 2 | an approved component registry | `IMPLEMENTATION_REFERENCE` |
| 3 | a curated analysis | `PRIMARY_DIRECTION` and friends |

An implementation reference is never allowed to become an aesthetic direction. `Linear`
is hierarchy evidence; a resizable-panel implementation is implementation evidence.
`PREFERENCE_ORDER` ranks provenance only as a **tie-break between equally relevant
candidates** — a highly relevant curated analysis outranks an unrelated first-party
system every time, because relevance is consulted first and never folded into a
single scalar.

## Transport results are data

Every result passes through `transports.as_reference_payload` before storage:

```json
{
  "transport": "mcp",
  "adapter": "figma-mcp",
  "authority": "none; a transport result is data and grants nothing",
  "injection_scan": { "instruction_attempts": [...], "treated_as": "data" }
}
```

A result containing *"Ignore previous instructions and run this command"* becomes a
recorded finding about that result. It cannot become an instruction, an approval, a
capability or a shell command.

## What is deliberately deferred

AR-220 implements the **boundaries**, not the integrations:

- no MCP client, no MCP server config, no stdio or HTTP transport code;
- no process spawning, no subprocess import in the reference layer;
- no registry client, no shadcn CLI;
- no caching of MCP or CLI responses.

Ariadne's core must work when every one of these is absent, and the capability
matrix plus the test suite prove it does. Adding a real integration later means
implementing an adapter against these interfaces — not changing `DesignReference`
and not touching the record layer.