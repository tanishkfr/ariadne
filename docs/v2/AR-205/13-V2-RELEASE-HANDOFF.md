# AR-205 — 13 — V2 release handoff (human-approved steps)

Nothing in this document has been executed. It is the exact operator sequence
for publishing Ariadne v2 after the human decides to ship.

## 0a. Recorded local candidate

Built with `python scripts/build-release.py --output dist` from release commit
`ced38012383e038e3a7bb900b029c835d7b64952` (the milestone-record commit adds
documentation only; no shipped runtime file differs).

| Artifact | SHA-256 |
|---|---|
| `ariadne-runtime-2.0.0rc1.zip` | `86c67a2777f6da1efaba6b0c93c8e3d7505750482e07c0e2bf55e3d350c62974` |
| `ariadne-2.0.0rc1-py3-none-any.whl` | `3e20a46d7378a2707ffe90acab5b7766d9def37a00b3afebb7006800c53c87f4` |
| `ariadne-release.json` | `391460df730e8f10a1452a6199799c931881c1dfe61f6305652d358e54bc364e` |
| `ariadne-2.0.0rc1-release-notes.md` | `fc641d1fc68957c0d242065818a3edcd37d84684e60efd91261613acacc3db66` |

Version `2.0.0rc1`; Python `>=3.10`; protocol version 1; run-state schema 1;
record schema 2. `release.artifact_problems("dist")` reports no problems.

## 0. Preconditions

- The AR-205 branch is merged or the release commit is checked out.
- `python scripts/release-check.py` is green with no `FAIL`.
- Logo/banner assets are final (raster crops are already in `assets/`).

## 1. Final version

```bash
# VERSION is already 2.0.0rc1 for the candidate. For the public release, set the
# final version (for example 2.0.0) and update the surfaces together:
#   VERSION, RELEASE-NOTES.md heading, README/QUICKSTART/INSTALL/GETTING-STARTED
#   wheel URLs, .agents/skills/ariadne/references/installation.example.json
python scripts/release-check.py --allow-dirty
```

## 2. Clean build

```bash
python scripts/build-release.py --output dist
python scripts/release-check.py --dist dist
```

Record from `dist/ariadne-release.json` and `dist/SHA256SUMS.txt`:

- version, source commit, build timestamp, Python compatibility;
- runtime zip, launcher wheel, release-notes digests;
- protocol version 1, run-state schema 1, record schema 2;
- benchmark result reference and release-check result.

## 3. Commit and tag

```bash
git add -A
git commit -m "AR-205: <final version> release candidate"
git tag v<final version>
```

## 4. Push and publish (human only)

```bash
git push origin <branch>
git push origin v<final version>
gh release create v<final version> dist/* --title "Ariadne <final version>" --notes-file dist/ariadne-<final version>-release-notes.md
```

If PyPI publication is ever approved, it requires the distribution-name decision
from ADR 0001 first; the current artifacts are not publishable to PyPI under the
`ariadne` name.

## 5. Verify after publication

```bash
python -m pip install --user "https://github.com/tanishkfr/ariadne/releases/download/v<final version>/ariadne-<final version>-py3-none-any.whl"
python -m ariadne install
python -m ariadne doctor
python -m ariadne --version
```

Verify the published digests against `SHA256SUMS.txt`.

## 6. Rollback procedure

- Installation rollback for users: `python -m ariadne rollback` (the previous
  verified version remains installed).
- Release rollback: mark the GitHub release as a pre-release or delete the
  release entry, restore the previous release as latest, and publish a note
  naming the defect. Do not rewrite tags that users may have installed from.
- Project migration rollback: `python -m ariadne migrate --rollback --project
  <project>` while no v2-only work exists; otherwise the preserved
  `ariadne-run.v*.bak` remains available for manual recovery.

## 7. Branding handoff

Place final vector assets in `assets/`:

```
assets/ariadne-mark.svg
assets/ariadne-wordmark.svg
assets/ariadne-banner.svg   (or a higher-resolution ariadne-banner.png)
```

The README references `assets/ariadne-banner.png`; replacing that file with the
final banner is the only edit needed.
