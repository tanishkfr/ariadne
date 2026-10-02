# Third-party notices - Ariadne 2.1 (AR-206)

## Scope

This file records the third-party position of the **Ariadne 2.1 native Decision
Runtime** (feature AR-206, branch `v2/2.1-native-decision-runtime`). It covers
`src/ariadne_engine/decisions/runtime/` and everything AR-206 added to the engine
contract, the integrations, the CLI and the test suites.

## The position, stated plainly

**AR-206 added no third-party runtime component and no third-party code.**

The reference bounded engine, its sidecar process, its transport, its weight
builder and its seed weights are original Ariadne code. The reference engine is
pure Python standard library. It ships no model file, downloads nothing, contacts
no network, and declares no dependency.

This is not an aspiration the packaging happens to satisfy; it is asserted by the
release tooling and the functional suite:

- `pyproject.toml` declares `dependencies = []` and `requires-python = ">=3.10"`,
  with an in-tree build backend (`ariadne_backend`) and no build requirements.
- A walk of the import graph across `src/ariadne/`, `src/ariadne_engine/`,
  `scripts/` and `build_backend/` resolves to the standard library only. (The one
  first-party package name outside `src/`, `arbench`, is Ariadne's own benchmark
  package under `benchmarks/`.)
- `scripts/test-decision-runtime.py` reads `pyproject.toml` and fails if any of
  `torch`, `transformers`, `safetensors`, `huggingface`, `onnxruntime`, `numpy`,
  `scikit-learn` or `scipy` appears.
- The same suite asserts the runtime package contains no trainer, and that the
  only module writing a weight file is the explicit seed builder.
- `docs/v2/AR-205/03-DISTRIBUTION.md` records the same zero-third-party-import
  result for released 2.0.

## The standard library modules used

AR-206 code imports only these, all from the Python standard library:

```
__future__    argparse      dataclasses    hashlib       json
math          ntpath        os            pathlib       platform
re            signal        subprocess     sys           threading
time          typing
```

By module, for the record:

| Module | Standard-library imports |
|---|---|
| `__init__.py` | `__future__` |
| `evaluation.py` | `__future__`, `hashlib`, `json`, `time`, `typing` |
| `export.py` | `__future__`, `hashlib`, `json`, `pathlib`, `typing` |
| `integrity.py` | `__future__`, `os`, `pathlib`, `platform`, `typing` |
| `manifest.py` | `__future__`, `hashlib`, `json`, `ntpath`, `pathlib`, `typing` |
| `observe.py` | `__future__`, `typing` |
| `profiles.py` | `__future__`, `dataclasses`, `hashlib`, `json`, `typing` |
| `promotion.py` | `__future__`, `typing` |
| `provider.py` | `__future__`, `typing` |
| `reference.py` | `__future__`, `dataclasses`, `hashlib`, `json`, `math`, `pathlib`, `re`, `typing` |
| `schema.py` | `__future__`, `dataclasses`, `hashlib`, `json`, `typing` |
| `seeds.py` | `__future__`, `pathlib`, `typing` |
| `selection.py` | `__future__`, `typing` |
| `session.py` | `__future__`, `os`, `pathlib`, `platform`, `typing` |
| `shadow.py` | `__future__`, `typing` |
| `shortlist.py` | `__future__`, `hashlib`, `json`, `re`, `typing` |
| `sidecar.py` | `__future__`, `argparse`, `json`, `pathlib`, `sys`, `typing` |
| `transport.py` | `__future__`, `json`, `os`, `pathlib`, `signal`, `subprocess`, `sys`, `threading`, `typing` |

`sidecar.py` also has a fallback absolute import of `ariadne_engine`, which is
Ariadne's own package, used only when the sidecar is launched by file path without
package context.

## The weights

The shipped weight file is **data, not code**, and its provenance is Ariadne's own.
`ariadne_engine.decisions.runtime.seeds.SEED_SOURCE` reads, verbatim:

> ariadne deterministic decision tables (ar-205d decision-intelligence
> answer-space vocabularies and projection contracts); rule-derived features, not
> a trained corpus

The families are fitted from rule-derived examples written against the projection
field names Ariadne's own `decisions.projections` module declares, over the
answer spaces Ariadne's own contracts already publish
(`DECISION_CLASSIFIABLE_FAILURE_CLASSES`, `REVIEW_ESCALATIONS`,
`EVIDENCE_RELEVANCE_ANSWERS`, `ROUTE_FAMILIES`). The installation is two JSON
files of roughly 97 KB in total.

**They are not trained parameters and they are not presented as such.** They are
feature encodings of rules the engine already knew. The weight file records its
source, the install output says "probabilities from this engine are uncalibrated
by construction", and every answer is labelled `PROVIDER_PROBABILITY`. A
consumer of this file should hold it to that description and no stronger one.

## The pre-existing 2.0 situation

Stated only as far as it is verifiable from this repository, and not overstated:

- **`pyproject.toml` has declared `dependencies = []` since 2.0.** There is no
  third-party dependency to attribute, before or after AR-206.
- **`src/` contains no third-party imports**, confirmed by AST scan above. The
  claim recorded in `docs/v2/AR-205/03-DISTRIBUTION.md` and
  `docs/v2/AR-205/12-AR-205-REPORT.md` - zero third-party imports in shipped code,
  no bundled third-party code - still holds after 2.1.
- **The launcher is first-party.** `src/ariadne/` is Ariadne's own installation,
  update, rollback and uninstall controller. It imports only the standard library.
- **`adapters/` is configuration, not code.** It is a set of markdown contract
  documents (`codex.md`, `claude-code.md`, `claude-reasoner.md`, `cursor.md`,
  `reasoner-contract.md`, `codex-baseline.md`, `SKILL.md`) and one JSON
  capability catalogue (`reasoners.json`). These describe how to drive *external*
  reasoning tools (the `codex` and `claude` executables). No third-party source is
  bundled, and nothing in them is a copy of a vendor's code - they are Ariadne's
  own interface contract.
- **The `JevShapedAdapter` is Ariadne's own interface, not a Jev client.**
  `src/ariadne_engine/decisions/providers.py` defines a vendor-shaped capability
  mapping (`JEV_SHAPED_CAPABILITIES`) and an injection-only adapter class. It
  performs no network call, requires no credential, is activated only when an
  operator supplies an interface object, and its live use is recorded as
  `NOT_EXECUTED`. It is released 2.0 surface, not part of AR-206, and no code from
  any Jev implementation is present in this repository. See
  `docs/v2/AR-205D/07-PROVIDERS.md`.
- **Optional external tools are not dependencies.** Where Ariadne can drive an
  external executable (a reasoning CLI), the executable is the user's to install
  and the feature is opt-in. Absence is recorded as capability state, never as a
  crash.

## No NOTICE file

Ariadne ships `LICENSE` (Apache License 2.0) and does not ship a `NOTICE` file.
Apache 2.0 section 4(d) requires a `NOTICE` file to be handled only when the work
includes one; because no third-party attribution notices exist for AR-206, none
is created here. This file is a provenance statement, not an Apache `NOTICE`
file, and carries no attribution obligations.

## If that ever stops being true

The honest failure modes are worth naming in advance:

1. a checkpoint-backed engine installed as a Decision Runtime, bringing its own
   licence and its own notices;
2. an operator-supplied embedding function passed to the `embedding` shortlist
   strategy;
3. a `JevShapedAdapter` activated against a live third-party service.

None of these is shipped by AR-206, and each is an explicitly external,
operator-supplied component. If one enters a distribution, it must be recorded
here with its licence, its notices and its attribution obligations before that
distribution ships. A dependency added silently inside `pip install ariadne` is
precisely the failure this architecture refuses.

See also `LAYA-ADAPTATION.md`, which records the adaptation question for this
feature specifically.
