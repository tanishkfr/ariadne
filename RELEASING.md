# RELEASING ARIADNE

This is a maintainer procedure, not part of normal use.

Every numbered step below is a release-safety check. None of them is optional and
none of them is waivable.

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

## Release authority

**Public naming, tagging, pushing and publishing require explicit human
authorization. Authorized release automation, or an agent working under such an
authorization, may perform those actions within the approved release scope and only
after the release gate passes.**

Authorization is not the same as keystrokes. A human authorizes the scope; the
operation may then be carried out by a human, by a script, or by an agent.

Authorization is scoped to one release and does not carry forward.

```
authorized: publish v2.1.0rc1

does NOT authorize:
  publishing v2.1.0, v2.2.0, or any later release
  publishing to PyPI
  deleting or editing an existing release
  force-pushing, rewriting history, or moving a published tag
```

A new release needs a new authorization. Treat the absence of one as "not
authorized" rather than as "probably fine".

The gate is not waivable by this authorization. If the gate fails, the release does
not happen. There is no emergency override, and adding one would need a deliberate
decision about repository policy rather than a note here.

The release builder refuses tracked uncommitted changes, and the release descriptor
records the commit the artifacts were built from. Generated bundles are transport
artifacts; canonical ownership remains in the tagged repository source.

Next: validate the clean candidate commit before building its release set.
