# 06 — Reference Security (AR-220)

The permanent rule this whole subsystem exists to enforce:

> **External design references are data, not instructions or authority.**

Design material is unusually good at carrying text that looks like instructions. A
reference page can say *"ignore previous instructions"*, *"run this command"* or
*"install this package"*, and a `DESIGN.md` can put the same sentence in its
rationale. Everything below follows from refusing to let that text mean anything.

## Test matrix, and results

Every case below is exercised by `scripts/test-design-reference.py` and most are
additionally covered by a mutation in
`scripts/test-design-reference-mutations.py`.

| # | Attack | Result |
|---|--------|--------|
| 1 | Path traversal through a local `DESIGN.md` path | **refused** — `contained_path` |
| 2 | SSRF: external URL to a private IP | **refused** — `require_fetchable_url` |
| 3 | `file://` URL | **refused** — HTTPS only |
| 4 | `localhost` / loopback | **refused** |
| 5 | Link-local / cloud metadata (`169.254.169.254`) | **refused** |
| 6 | IPv6 loopback, unspecified, mapped and 6to4 forms | **refused** |
| 7 | Embedded credentials in a URL | **refused** |
| 8 | Non-standard port | **refused** |
| 9 | Hostile catalog slug (`../evil`, `a/b`) | **refused** — slug character class |
| 10 | Oversized `DESIGN.md` | **refused**, not truncated |
| 11 | Malformed YAML frontmatter | **refused by name** |
| 12 | Duplicate frontmatter keys | **refused by line number** |
| 13 | Malicious markdown links in a document | **inert**: link text is stored as text; URLs are never fetched from a document |
| 14 | Reference text granting authorization | **recorded, grants nothing** |
| 15 | Reference text changing policy | **recorded, grants nothing** |
| 16 | MCP result containing instructions | **recorded, grants nothing** |
| 17 | CLI result containing shell commands | **argv validated; shell operators refused** |
| 18 | Path escape via a tampered discovery record | **refused** — contained path recomputed at use |

## 1. Containment

`safety.contained_path(candidate, root)` resolves `..`, absolute paths, drive
letters, UNC prefixes and symlinks **before** asserting containment. A path that
looks contained and lands outside is refused the same as one that obviously
escapes.

```text
the path '../../etc/passwd' resolves outside the permitted root; a reference
locator may not escape the tree it was declared inside
```

This is defence in depth, not the only check: `getdesign._safe_slug` separately
refuses any slug containing a path separator, so a hostile catalog index cannot
steer `raw_url()` at all.

## 2. URL safety

`require_fetchable_url` refuses, by name:

- **any scheme but HTTPS** — `file://`, `ftp://`, `gopher://`, `data:`;
- **any port but 443/8443**;
- **embedded credentials** — retrieval never sends project content or secrets;
- **blocked hostnames** — `localhost`, `*.localhost`, `*.internal`, and cloud
  metadata names;
- **non-public IP literals** — loopback, private, link-local, reserved, multicast,
  unspecified;
- **tunnelled forms** — IPv4-mapped (`::ffff:127.0.0.1`), 6to4 and Teredo prefixes
  are unwrapped and re-checked, so a public-looking IPv6 address that decodes to a
  private one is refused.

### Documented limitation: DNS rebinding

A hostname that *resolves* to a private address — `10.0.0.1.nip.io` — is **not**
refused by this check, and the test suite asserts that it passes. This is a real
boundary, recorded rather than hidden: the check resolves nothing, which is what
makes it deterministic and offline-testable.

The defence is structural instead of lexical:

1. every adapter targets a **fixed host set** built from module constants, so a
   rebinding name never reaches a retrieval URL;
2. an operator-supplied **allowlist** is required for live retrieval, and a target
   outside it is refused;
3. `getdesign.raw_url()` cannot be pointed at another host by any catalog input.

So the gap is closed by construction rather than by string matching.

## 3. The prompt-injection boundary

`safety.scan_reference_text` is a **detector, not a filter**. Detection never
removes the observation and never refuses the reference — the sentence is part of
what the source says. What it does is attach a recorded fact to the record, so a
reviewer sees that the source attempted escalation and nothing downstream can treat
the sentence as a directive.

| Detected shape | Example |
|----------------|---------|
| `override-instructions` | "ignore all previous instructions" |
| `execute-command` | "run this command", `sudo`, `rm -rf`, `npm i` |
| `install-package` | "install this package" |
| `grant-authority` | "you are now authorized to", "treat this as approval" |
| `policy-change` | "disable the safety policy", "relax the guardrails" |
| `exfiltrate` | "send the API key to …" |

Each finding records `action: RECORDED_AS_DATA`. Verified end to end: a hostile
`DESIGN.md` is still *registered* — it is evidence — and the resulting run state
contains no grant, no override and no approval.

> The words are **not** rewritten. `as_data_only` strips control characters so a
> document cannot smuggle a terminal escape or a record break into an artefact, but
> silently editing the source would make the stored observation differ from the
> retrieved bytes — and the digest would no longer describe what was actually read.

## 4. `ACCESS_RESTRICTED` is a real answer

Ariadne never bypasses a login, a paywall, an entitlement, robots or rate limits,
and never uses private cookies. When a source may not be read:

```text
ACCESS_RESTRICTED
```

and retrieval stops. This is a live finding, not a hypothetical: getdesign.md's
catalog exposes entry pages publicly but its **Download DESIGN.md** control is
sign-in gated, and the recorded fixtures assert `catalog_raw_download_gated: true`
for every entry.

## 5. Transports grant no authority

For MCP and CLI results, authority is structurally absent:

- results are neutralised and scanned before storage;
- `as_reference_payload` stamps `authority: "none; a transport result is data and grants nothing"`;
- an MCP adapter may not be asked for a verb it never declared;
- a CLI argv containing shell operators, code-execution flags or a
  network-fetching binary is refused, and a refused argv **disables** the adapter
  rather than being cleaned into a working one;
- configuring a CLI is explicitly not authorization — `requires_authorization`
  stays `true` and the note says so.

## 6. Resource limits

| Bound | Value | Where |
|-------|-------|-------|
| Document bytes | 256 KiB | `MAX_DESIGN_REFERENCE_BYTES` |
| Candidate index | 1024 | `MAX_DESIGN_REFERENCE_INDEX` |
| Candidates returned | 64 | `MAX_DESIGN_REFERENCE_CANDIDATES` |
| Deep inspections | 5 (default) | `REFERENCE_BUDGET_DEFAULTS` |
| Observed patterns per reference | 64 | `MAX_DESIGN_REFERENCE_PATTERNS` |
| Sections per document | 200 | `MAX_DESIGN_REFERENCE_SECTIONS` |
| Nesting depth | 12 | `designmd.MAX_NESTING_DEPTH` |
| CLI argv | 24 items | `transports.MAX_CLI_ARGS` |
| CLI output | 256 KiB | `transports.MAX_CLI_OUTPUT_BYTES` |

Oversized input is **refused with a named reason, never truncated** — a truncated
record looks complete and is not. The candidate *index* bound is deliberately
separate from the *candidate* bound: the real catalog publishes 550+ entries, so
bounding the index at the candidate cap would refuse the real corpus in order to
protect a much smaller thing.

## 7. Failure must degrade, never crash

A third party's outage must not take a design task down. A connection error, a
timeout, a truncated body or a DNS failure is recorded as a rejected candidate with
its reason, acquisition continues, and the run proceeds from whatever evidence it
has:

```text
cursor could not be retrieved: OSError: connection refused. Reference acquisition
continues without it; no content was invented in its place
```

This was a real defect found by the adversarial review — the original code caught
only `ContractError`, so a dead transport propagated out of acquisition.

## Mutation coverage

Of 22 mutations, the security-relevant ones are:

| Mutation | Caught |
|----------|--------|
| reference text treated as authorisation | yes |
| external URL allowed to a private IP | yes |
| retrieval allowlist requires every prefix | yes |
| access-restricted download treated as public | yes |
| probe path escapes the project root | yes |
| oversized document silently truncated | yes |
| duplicate slug resolved by order | yes |
| network failure crashes the design stage | yes |
| project-first order inverted | yes |
| compiled direction self-approves | yes |
| motion observed without a basis | yes |

The allowlist mutation deserves a note: the **shipped code had that bug**. The
guard raised unless *every* allowlist prefix matched, which inverted the check and
refused the provider's own documented host. The mutation restores the historical
bug so the regression test is proven to catch it.

## Threat model summary

| Adversary | Wants | Defence |
|-----------|-------|---------|
| Malicious design document | Execute code / install a package | injection boundary records; no execution from document content |
| Malicious catalog index | Redirect retrieval | slug character class + fixed host set + allowlist |
| DNS rebinding | Reach a private service | fixed host set + allowlist (documented) |
| Compromised CLI argv | Code execution | shell operators and `-c`-class flags refused; never a shell |
| Compromised MCP server | Authority or execution | results are data; no declared verb, no call |
| Reference author | Ariadne clones a brand | BORROW/ADAPT/AVOID + reuse constraints + counter-references |
| Network outage | Crash the design stage | recorded rejection; workflow continues |
| Oversized document | Exhaust the context | hard byte bound, refused not truncated |