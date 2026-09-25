# AR-205 — 10 — Release notes draft

The draft lives at [RELEASE-NOTES.md](../../../RELEASE-NOTES.md) so that the
release builder can copy it into the artifact directory unchanged. It is the
candidate's public description and states:

- what v2 adds (executable orchestration, adaptive execution, design
  intelligence, verification hardening, the Decision Plane, economics
  instrumentation, migration, a standalone API);
- what stays experimental and why (no live quality comparison exists);
- the migration commands;
- the distribution-name decision and the PyPI deferral;
- known limitations, including the contract-verified-only Boreal status and the
  absence of artifact signing;
- the evidence limits: deterministic offline tests, no model-quality claim.

The release gate checks that the notes name `VERSION`, carry the platform and
first-time-user comprehension tokens, and contain no claim stronger than the
test record.
