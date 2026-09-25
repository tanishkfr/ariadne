# AR-205 — 11 — Launch checklist

Human-readable ship checklist. Engineering items are marked from the recorded
results; human-only items are intentionally unchecked.

## Engineering (AR-205, verified locally)

- [x] final source review (bounded adversarial pass, one repair cycle)
- [x] all prior AR-200–AR-204 benchmarks remain green
- [x] release benchmark subset green (`--release`, 45 cases)
- [x] release gate green (`scripts/release-check.py`)
- [x] clean wheel install verified in an isolated environment (14/14)
- [x] migration dry run verified
- [x] migration apply verified
- [x] rollback verified, including the refusal after v2-only work
- [x] public API and CLI documented and import-tested
- [x] integration contract verified against deterministic fixtures
- [x] known limitations reviewed and documented
- [x] experimental defaults reviewed and enforced as opt-in
- [x] version consistent across `VERSION`, packaging, runtime, docs and examples
- [x] branding assets present (`assets/ariadne-banner.png` and crops)
- [x] README final review
- [x] release notes draft written
- [x] release candidate artifacts built and hashed
- [x] release gate green with `--dist dist` (clean-tree confirmation follows the record commit)

## Human decisions (not performed by AR-205)

- [ ] logo/banner final vector files added (if desired; raster crops are in place)
- [ ] release notes approved
- [ ] G4 (ship) approval
- [ ] G5 (publish) approval
- [ ] tag approved
- [ ] publish approved
- [ ] PyPI namespace decision scheduled (distribution name stays `ariadne`
      until then; see ADR 0001)

## Known limitations acknowledged by the human

- no live provider-quality comparison; behavior-sensitive AR-204 flags stay off
- Boreal compatibility is contract-verified only, not live-verified
- no cryptographic artifact signing or pinning
- no OS sandbox or run-state attestation
- migration rollback is unavailable once a migrated run has v2-only work

## After publishing (human)

- [ ] verify the release page artifacts against `SHA256SUMS.txt`
- [ ] install the published wheel on a clean machine and run `doctor`
- [ ] record the publication in `CHANGELOG.md` if the final version differs
- [ ] if anything fails, roll back the release page and publish the rollback
      procedure from `docs/v2/AR-205/13-V2-RELEASE-HANDOFF.md`
