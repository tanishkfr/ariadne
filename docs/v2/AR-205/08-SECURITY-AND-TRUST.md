# AR-205 — 08 — Security and trust (milestone record)

The public-facing statement is [TRUST.md](../../guides/TRUST.md) at the repository
root. This page records what AR-205 verified, and what remains a documented
boundary rather than a claim.

## Verified in this milestone

| Invariant | Where it is tested | Result |
|---|---|---|
| Migration cannot create authority (51) | release suite migration cases; benchmark `migration.*`, `security.migrated-legacy-gate-refused` | PASS |
| Package installation must not depend on maintainer-only files (52) | wheel install suite; `build-release.py --self-test`; artifact private-path scan | PASS |
| Version disagreement fails the release gate (53) | release suite mutations; `release-check.py` version check | PASS |
| Integration adapters cannot bypass transition authority (54) | `integration-contract.adapter-cannot-fabricate-validation`; adapter design (no verification operation) | PASS |
| Protocol incompatibility fails explicitly (55) | negotiation fixtures for above/below range and missing capability | PASS |
| Experiments stay opt-in without quality evidence (56) | `release.experimental_defaults_problems`; gate mutation test | PASS |
| Missing optional providers do not break installation (57) | wheel install without providers; public-API import test | PASS |
| Artifacts must match their manifest (58) | `release.artifact_problems`; stale-hash mutation test | PASS |
| Rollback never silently destroys source state (59) | migration rollback preserves the migrated bytes and refuses after v2 work | PASS |
| Public docs cannot claim stronger evidence than tests show (60) | release notes and trust document name Boreal as contract-verified only | PASS |

## Adversarial pass (bounded, one cycle)

Attempts made against the candidate and their outcomes:

1. **A v1 approval becomes a v2 approval.** Refused by design: migration copies
   the approval list verbatim and records `approvals_created: 0`; the legacy
   gate in `DESIGN.md` stays unapproved (`security.migrated-legacy-gate-refused`).
2. **An old review becomes current verification.** Refused: verification records
   bind a revision and are freshness-checked; a changed artifact reports `STALE`
   (`false-acceptance.stale-passing-evidence-does-not-close`).
3. **Package imports from the development checkout.** Tested by the isolated
   wheel install: the installed runtime is self-contained and the launcher fails
   if the runtime manifest is missing.
4. **Package contains private maintainer files.** `build-release.py --self-test`
   and `release.artifact_problems` scan the runtime zip; the release suite checks
   the allowlist excludes validation/operations/tests and the test tooling.
5. **Package and runtime versions differ.** `release.version_problems` compares
   `VERSION` with the wheel metadata, runtime output and documents; the gate
   fails on any disagreement (mutation-tested).
6. **Consumer bypasses transition authority.** The adapter exposes no operation
   that writes verification, approval or review records directly.
7. **Protocol mismatch silently continues.** `negotiate` refuses out-of-range
   versions and missing required capabilities before any operation runs.
8. **Missing optional provider crashes startup.** Import and wheel tests run
   without any optional provider; capability state reports absence instead.
9. **Stale artifact hash passes the release gate.** Mutation test corrupts the
   descriptor and the gate reports the mismatch.
10. **Rollback deletes the only valid state.** Rollback copies the migrated
    state aside first and restores only the preserved backup.
11. **Experimental optimization enables itself.** Defaults are checked on every
    release run; the mutation test flips a default and the gate fails.
12. **Quick start only works because repository files are present.** The wheel
    install suite performs doctor, install, project start and uninstall from an
    isolated environment.

## Defect found and fixed

The failure/repair golden workflow exposed a real retry defect: an escalated S4B
attempt inherited the previous attempt's baseline, which predated the previous
attempt's engine-written return file, so validation classified that file as an
out-of-scope worker change (`AUTHORIZATION_FAILURE`) and blocked a legitimate
repair. The fix adds every recorded packet's return path to the in-scope
evidence patterns for the validation scope check
(`scripts/ariadne.py`, `validate_worker`); the golden workflow now passes
end to end and the worker's implementation scope is unchanged.

## Data handling

Run state and evidence never store provider credentials. Files whose paths are
classified sensitive (`.env` and similar root-level credential names) are
fingerprinted by size and modification time without reading their contents, and
rendered requests redact detected secret patterns. This is a storage rule, not a
secret scanner: a credential pasted into ordinary project text is project text.

## Boundaries that remain

- No OS sandbox, no cryptographic attestation of local files, no protection from
  a malicious local process, no truth about an unreported provider observation,
  no immunity to prompt injection inside a model's own authority.
- Artifact signing and pinning are deferred and stated in the launch checklist.
- Live Boreal verification remains unexecuted.
