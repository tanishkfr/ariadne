# AR-205 — 03 — Distribution, packaging and integrity

## Strategy

The distribution is the same launcher-then-runtime model as v1.6.7, versioned
for v2:

```
ariadne-2.0.0rc1-py3-none-any.whl        # launcher: ariadne/ + seed-runtime.zip
ariadne-runtime-2.0.0rc1.zip             # runtime tree + RELEASE-MANIFEST.json
ariadne-2.0.0rc1-release-notes.md
ariadne-release.json                     # descriptor with artifact hashes
SHA256SUMS.txt                           # all four files
```

The distribution name decision is recorded in
[adr/ADR-0001-distribution-name-strategy.md](adr/ADR-0001-distribution-name-strategy.md):
keep the name for the GitHub-release channel, defer PyPI with an explicit
warning, and treat PyPI publication metadata as a release-gate failure.

## Build

```bash
python scripts/build-release.py --output dist
```

The builder refuses a dirty tracked tree unless `--allow-dirty` is passed
(development only), reads the version from `VERSION`, records the source commit,
and writes the descriptor and checksums. `--self-test` builds a bundle in a
temporary directory and asserts that no private tree, credential, local path or
maintainer fixture is included (18/18 checks at this revision).

Runtime contents are allowlisted (`RUNTIME_TOP_LEVEL`, `RUNTIME_TREES`,
`RUNTIME_SCRIPTS`). `validation/`, `operations/`, `tests/` and the release test
tooling are not part of the runtime; the engine modules added in AR-205
(`migration.py`, `public.py`, `integration.py`, `release.py`) are.

## Integrity checks

`ariadne_engine.release.artifact_problems(directory)` verifies, without network
access:

- the descriptor version equals `VERSION`, and its product is Ariadne;
- the runtime zip digest equals `sha256` in the descriptor;
- the launcher and release-notes digests match their descriptor entries;
- `SHA256SUMS.txt` authenticates every artifact;
- the embedded `RELEASE-MANIFEST.json` version and source commit agree with the
  descriptor, and every listed file digest matches the real zip content;
- the runtime zip contains no private path;
- the launcher carries `ariadne/seed-runtime.zip` and the Apache-2.0 licence.

`scripts/release-check.py` runs that verification when `--dist` points at built
artifacts, and reports `NOT_EXECUTED` when no artifacts exist.

## Licence and dependency audit

| Item | Finding |
|---|---|
| Project licence | Apache-2.0 (`LICENSE`; declared in `pyproject.toml`, carried in the wheel licences directory) |
| Runtime dependencies | none (`dependencies = []`, `optional-dependencies = {}`); the launcher enforces a minimum Python contract and nothing else |
| Third-party imports in shipped code | none: `src/ariadne`, `src/ariadne_engine` and `scripts/` import the standard library only (AST scan over every shipped module) |
| Bundled assets | the brand crops in `assets/` (maintainer-supplied; not shipped in the runtime) and repository-authored Mermaid/text fixtures |
| Optional provider references | documentation and capability metadata only; no provider SDK is installed, bundled or required |
| Code copied from other projects | none; the recorded Boreal audit informed design decisions but no Boreal code was ported |

Consequences: the runtime is offline by construction, the wheel has no
transitive licence surface, and a clean install cannot pull a dependency the
maintainer did not approve.

## Honest limits

- **No cryptographic signing.** Artifacts are authenticated by digest and by the
  embedded manifest, not by a maintainer key. Signing and pinning are deferred
  and stated as such in the release notes and launch checklist.
- **Hashes are not provenance.** The source commit is recorded from the build
  environment; it is evidence for a human, not an attestation chain.
- **No public upload.** Nothing in this milestone publishes, tags or pushes.
  The handoff document lists the exact human steps.
