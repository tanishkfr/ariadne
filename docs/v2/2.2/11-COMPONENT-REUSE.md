# 11 — Component Reuse

> **Reuse what already exists before generating something new.**

A model asked to "build a panel" will happily write a new panel, and the result is a
repository with two panels, one of which has the fix for the bug found last month.

## The inventory runs first

Before any component decision is made, the engine reads the repository rather than
asking anyone what it contains:

```text
design_tokens     CSS custom properties with values, Tailwind colour keys, font stacks
components        every component file, its exports, digests, token usage
primitives        buttons · forms · navigation · dialogs · panels
                  icons · toolbars · typography
layout            grid and stack utilities, and where they came from
motion            keyframes, transition declarations, reduced-motion handling
registry          any component registry or config the project declares
project_identity  design documents, discovered through AR-202D
```

Read-only, offline. It walks declared component directories and reads files by name. It
does not run a build, resolve a dependency graph, contact a registry, or install
anything.

### The directory list

Two additions to AR-220's, both forced by running the inventory against a real project:

* `EXTRA_TOKEN_FILES` — AR-202D's list covers the common React/Next/Vite placements. A
  project keeping its tokens at `src/styles/tokens.css` reported **zero** CSS
  variables from a file sitting in a directory named `styles`. That is not an exotic
  layout, and a scan that misses it turns "this project has no tokens" into a false
  statement.
* `EXTRA_COMPONENT_DIRS`, plus a **bounded fallback scan** when the declared
  directories yield nothing. "No component files" is the most consequential false
  answer this module can give, because it turns every reuse decision into
  `BUILD_CUSTOM`. The fallback descends two levels, skips `node_modules`, and records
  that it ran — so a negative result is checkable rather than merely reported.

### `node_modules` is never the project

The skip set is structural, and `node_modules` is the important entry in it: it contains
other people's components, and counting them as the project's own is exactly the
confusion this module exists to prevent.

## The decision

Four possibilities, in preference order:

| Decision | When |
|---|---|
| `REUSE_PROJECT_COMPONENT` | the project already ships it, unchanged |
| `ADAPT_PROJECT_COMPONENT` | the project ships something close; it is extended, not replaced |
| `USE_APPROVED_REGISTRY_COMPONENT` | nothing local fits **and** an approval is recorded |
| `BUILD_CUSTOM_COMPONENT` | the fallback, and the one that must be justified |

The order is the decision procedure, not a ranking of desirability. External registries
are last on purpose, and there is no configuration that skips the ladder: a caller who
wants a registry component has to have found nothing local first, and has to hold the
approval.

Each decision records the rung that answered it:

```json
{
  "need": "Panel",
  "decision": "REUSE_PROJECT_COMPONENT",
  "existing_component": "src/lib/ui.ts",
  "reason": "the project already ships src/lib/ui.ts exporting Panel; generating a replacement would leave two implementations of one primitive",
  "rung": "existing-project-component",
  "replacement_refused": "an existing project component is never replaced without a recorded reason"
}
```

`BUILD_CUSTOM_COMPONENT` records *why* the registry was not chosen:

```json
"registry_refused": "no registry component was selected because no approval is recorded; a registry is a candidate source, not a default"
```

## Optional registry and CLI use

When a project declares a registry (`components.json`), the engine reads the
declaration and records the entries. It never resolves, downloads or installs from it:

```json
{
  "declared": true,
  "available": false,
  "install_authority": "none — human G2 required",
  "reason": "a project component registry is a candidate source. Ariadne reads its declaration and never resolves, downloads or installs from it"
}
```

`available: false` is a first-class answer, not a failure. A registry that would need a
network call or a package manager is recorded as declared-but-unavailable, and the
component ladder's `INSTALL_AUTHORITY` stays `none` throughout.

## Dependencies

A reference that uses a library is evidence the library exists, not authorisation to
add it. There is no code path in this layer that installs anything — that is structural
rather than a policy someone could relax later.

```python
inventory.dependency_request(
    need="a resizable inspector divider",
    package="shadcn-ui resizable panels",
    requested_by="implementation reference for the divider contract",
)
# {
#   "status": "REFUSED_PENDING_HUMAN_G2",
#   "installed": False,
#   "approval_id": "",
#   "install_authority": "none — human G2 required",
# }
```

An approval id that appears *inside reference text* is not an approval, and the
function has no way to receive one that isn't.

## Licence and reuse boundary

```text
source                 who it is
license                the licence name
revision               what it was inspected at
files_inspected[]      what was actually read
reuse_status           INSPECT_ONLY · REUSE_ALLOWED · REUSE_WITH_ATTRIBUTION
                       · REUSE_RESTRICTED · UNKNOWN
attribution_required   what the licence actually demands
aesthetic_inherited    whether its appearance was adopted
code_copied            always False from this layer
pattern                the thing it taught, as a pattern
```

Rules:

* `UNKNOWN` is a real answer and the least convenient one. An unrecorded licence is an
  unrecorded licence.
* `REUSE_ALLOWED` and `REUSE_WITH_ATTRIBUTION` both require a **named** licence;
  reuse permission without one is refused.
* `REUSE_WITH_ATTRIBUTION` additionally requires non-empty attribution text. An empty
  attribution requirement is no requirement.
* `aesthetic_inherited` defaults `false` and is stated explicitly, because using an
  implementation pattern does not adopt its source's appearance — and because "we only
  took the code" is a claim that has to be on the record to be checkable.

## Evidence from the vertical slice

The fixture project is a real TypeScript front end with its own primitives in
`src/lib/ui.ts` (`Panel`, `Button`, `NavItem`, `Toolbar`, `Divider`, `logTable`),
its own icons, its own density helpers, and its own tokens. The inventory found 5
component files and 28 CSS variables, and the decisions were:

```text
Panel        REUSE_PROJECT_COMPONENT
Button       REUSE_PROJECT_COMPONENT
NavItem      REUSE_PROJECT_COMPONENT
Toolbar      REUSE_PROJECT_COMPONENT
Divider      REUSE_PROJECT_COMPONENT
IconButton   REUSE_PROJECT_COMPONENT
DataTable    BUILD_CUSTOM_COMPONENT     ← nothing in the project provides one
```

Six reused, one created. `src/lib/ui.ts`, `src/lib/icons.ts` and
`src/styles/tokens.css` were in `FORBIDDEN_SCOPE` for the whole run: reusing the
components and protecting the identity that makes reuse meaningful are the same
discipline.

## Read it

```bash
python scripts/ariadne.py design-component-inventory --run-root <run>
```

```python
from ariadne_engine import api
view = api.inspect_component_inventory(state)   # PROVISIONAL
```

Next: [12 — Design Implementation Provenance](12-DESIGN-IMPLEMENTATION-PROVENANCE.md)