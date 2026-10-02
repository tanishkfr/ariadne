# RELEASING ARIADNE

This is a maintainer procedure, not part of normal use.

1. Confirm the public destination is `tanishkfr/ariadne`, the private canonical
   source is `tanishkfr/ariadne-maintainer`, and GitHub is authenticated only as
   `tanishkfr`.
2. Confirm [LICENSE](LICENSE) and package metadata still declare the
   human-approved Apache-2.0 licence.
3. Update the single authoritative [VERSION](VERSION) and [CHANGELOG.md](CHANGELOG.md).
4. Start from a clean tracked worktree and run the complete validation recorded
   in the current private readiness report.
5. Build the release set:

   ```bash
   python scripts/build-release.py --output dist
   ```

6. Verify the wheel, runtime archive, descriptor, versioned release notes,
   individual checksums and `SHA256SUMS.txt`. Install the wheel into a fresh
   environment and run the stranger test.
7. Tag that exact commit as `vX.Y.Z`. Create one draft GitHub release, attach all
   generated files, then publish it. Prefer an immutable release when available.
8. Export only product/runtime source and user documentation to the public
   repository. Exclude validation runs, fixtures, tests, readiness reports,
   operations logs, maintainer notes and machine-specific paths.
9. Verify the public asset against its local file and run the README install in
   a machine or VM without the source checkout.

The release builder refuses tracked uncommitted changes. Generated bundles are
transport artifacts; canonical ownership remains in the tagged repository
source. Public naming, tagging, pushing and publishing remain human actions.

Next: validate the clean candidate commit before building its release set.
