# RELEASING BUILDER OS

This is a maintainer procedure, not part of normal use.

1. Decide and add the public licence. Do not publish while `pyproject.toml`
   contains `Private :: Do Not Upload`.
2. Update the single authoritative [VERSION](VERSION) and [CHANGELOG.md](CHANGELOG.md).
3. Start from a clean tracked worktree and run the complete validation listed in
   [V1.5.1-READINESS.md](V1.5.1-READINESS.md).
4. Build the release set:

   ```bash
   python scripts/build-release.py --output dist
   ```

5. Verify the wheel, runtime archive, descriptor and checksum files. Install the
   wheel into a fresh environment and run the stranger test.
6. Tag that exact commit as `vX.Y.Z`. Create one draft GitHub release, attach all
   generated files, then publish it. Prefer an immutable release when available.
7. Verify the public asset against its local file and run the README install in
   a machine or VM without the source checkout.

The release builder refuses tracked uncommitted changes. Generated bundles are
transport artifacts; canonical ownership remains in the tagged repository
source. Publishing the release and choosing a licence are human actions.

Next: obtain explicit release authority before creating the tag or GitHub release.
