# Provenance record: was the Ariadne 2.1 Decision Runtime adapted from Laya?

Feature: **AR-206**, Ariadne 2.1 native Decision Runtime.
Branch: `v2/2.1-native-decision-runtime`
Baseline for the comparison: `413b4ef` (*Release Ariadne 2.0.0*).
Date of record: 2026-10-01.

## Conclusion

**No. Nothing in AR-206 was copied, adapted, ported, vendored or derived from
Laya, or from any Jev or ConvAI implementation.**

The reference bounded engine, its sidecar process, the transport, the weight
builder and the seed weights are original Ariadne code, written for this feature.

This is a positive finding from a search, not an assumption. The searches and
their results are below, so the claim can be re-checked.

## What was searched

### 1. The AR-206 delta, file by file

```
git diff --stat 413b4ef..HEAD
```

53 files, 21,866 insertions, 55 deletions across three commits:

```
9c7528f  AR-206: native Decision Runtime (reference bounded engine, sidecar,
         shadow, calibration, promotion)
5f66fc6  AR-206: observe the native Decision Runtime in the four real integration paths
dbbbe76  AR-206: test the Decision Runtime, and fix what the tests found
```

`git log --all -- src/ariadne_engine/decisions/runtime` returns exactly those three
commits. There is no fourth, and no merge that brought in outside work.

Every file in that delta was read for the tokens `laya`, `convai` and `jev`
(case-insensitive). Result: **one file contains any of them as an added line -
`scripts/test-decision-runtime.py`** - and all occurrences are the assertions that
AR-206's product surface names no vendor:

```python
forbidden = ("laya", "jev", "convai")
check(f"{label} names no vendor", not any(
    token in text.lower() for token in ("laya", "jev", "convai")))
check("the install output names the implementation, not a vendor",
      "ariadne-reference-bounded" in installed.stdout
      and not any(token in installed.stdout.lower() for token in ("laya", "jev")))
```

plus one comment explaining that the released 2.0 `jev_shaped` provider contract
is pre-existing surface that 2.1 must not remove. Those strings are the *test* of
this claim, not evidence against it.

### 2. The runtime package specifically

All 18 files in `src/ariadne_engine/decisions/runtime/` were scanned for
`laya`, `jev` and `convai`: **zero occurrences**. The suite asserts this
permanently, over both the package source and the `decision-runtime` CLI command
block, and the check is in the release gate.

The only vendor-adjacent line anywhere under `src/` in the delta is one word in a
docstring in `src/ariadne_engine/decisions/__init__.py`, naming the *pre-existing*
AR-205D adapter: "boundary, and the Jev-shaped mapping adapter". It describes
2.0 surface and adds no code.

### 3. The whole repository, all branches

A word-boundary search for `laya` across every tracked file and every ref returns
**nothing**.

An earlier substring search appeared to hit four files (`ROUTER.md`,
`modes/game-experiment.md`, `prompts/project-start.md`, and the test script). Those
three non-test hits are the English word **"playable"** - as in "a playable or
experimental piece" - which contains the letters `laya`. Confirmed by running the
same search with a word boundary.

### 4. The whole history, all refs

`git log --all -S "laya"` returns four commits: `dbbbe76` (AR-206, the assertions
above) and `5176681`, `f1645e1`, `77658cf`. Checking each of those three older
commits with a word-boundary search returns **zero** occurrences - all three hits
are "playable".

`git log --all -S "convai"` returns exactly one commit, `dbbbe76`, for the
assertion list.

`git log --all -S "JevShaped"` returns three commits: `1d65bf7` (AR-205D, which
introduced the adapter - released 2.0 surface), `413b4ef` (Release 2.0.0), and
`9c7528f` (AR-206, which mentions it in a comment and in a test assertion that it
remains available). No AR-206 code depends on it.

### 5. Vendored material

- No `.gitmodules`: there are no submodules.
- No `.patch`, `.diff`, `.orig` or `.rej` files anywhere in the tree.
- No copyright, licence, `SPDX-License-Identifier`, "Adapted from", "ported from"
  or "vendored from" header in any of the 18 runtime modules.
- No directory of vendored source, and no binary artefact in the feature.

### 6. Dependencies

An AST scan over every module in `src/ariadne/`, `src/ariadne_engine/`,
`scripts/` and `build_backend/` finds **no non-stdlib import at all**.
`pyproject.toml` declares `dependencies = []`. There is nothing to attribute
because there is no third-party code in the feature, in the engine, or in the
launcher. Details in `THIRD_PARTY_NOTICES.md`.

### 7. The runtime's own declared provenance

The shipped weights state where they came from, in the weight file's own `source`
field and in the seed builder's `SEED_SOURCE`:

> ariadne deterministic decision tables (ar-205d decision-intelligence
> answer-space vocabularies and projection contracts); rule-derived features, not
> a trained corpus

The training examples are written against the projection field names Ariadne's own
`decisions.projections` module declares, over the answer spaces Ariadne's own
contracts publish. The four seeded families and their 73 rule examples are, in
total, Ariadne's own decision tables restated as features.

## Where the resemblance comes from, and why it is not copying

AR-206 shares vocabulary with the Jev-shaped adapter because both describe the
same *category* of thing - a bounded decision service with a small closed answer
space - and that vocabulary is Ariadne's own (`CONFIDENCE_KINDS`, the four bounded
primitives, `DECISION_CLASSIFICATIONS`). Shared domain vocabulary between two
independent implementations of the same idea is not derivation.

The two are also kept apart deliberately, and that separation is tested:

- the Decision Runtime uses **no** Jev-shaped capability labels, no
  `JevShapedAdapter`, and no external service;
- it carries its own provider identity, `local-bounded-runtime`, whose
  `LOCAL_PROVIDER_NAME` is `ariadne-decision-runtime`, and the suite asserts that
  identifier names the *kind* of implementation rather than a vendor;
- the 2.0 adapter remains, untouched, because removing released surface is not
  this feature's business.

## What would change this answer

A clean bill of health is only as good as the search behind it. Any of the
following would invalidate this record and require it to be rewritten before the
next distribution:

1. a commit on this branch, or a merge into it, that adds code or data from a
   third-party bounded-runtime implementation;
2. a non-stdlib import appearing in `src/` or `pyproject.toml`;
3. a checkpoint, weight file or embedding model whose bytes did not originate
   from `seeds.py` or an explicitly reviewed, separately licensed artefact;
4. any copy of a vendor capability vocabulary into the Decision Runtime package.

If you are reviewing this record and one of those is true, that is a licensing
problem, not a documentation problem, and it should be raised before release.

## Where to look

```
src/ariadne_engine/decisions/runtime/seeds.py       the declared provenance
src/ariadne_engine/decisions/runtime/__init__.py    the feature's own invariants
scripts/test-decision-runtime.py                    the product-checks section
THIRD_PARTY_NOTICES.md                              dependencies, per module
docs/v2/2.1/overview.md                             what is and is not built
docs/v2/AR-205D/07-PROVIDERS.md                    the pre-existing 2.0 adapter
```
