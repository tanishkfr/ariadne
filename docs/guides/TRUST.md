# Trust boundaries

Ariadne records what happened and enforces its own rules. It does not protect
your machine. This page states both sides precisely, so a decision to rely on it
is made with the real guarantees in view.

## What Ariadne can enforce

- **State transitions.** The permitted stage and lifecycle transitions are code.
  An illegal jump is refused; a refused transition changes nothing.
- **Approval binding.** A human approval names the gate, the target, the
  revision it approved and the identity that granted it. A changed revision
  invalidates the binding without deleting the record.
- **Single-use acceptance.** An acceptance spends one approval; a replay is
  refused.
- **Evidence contracts.** A verification claim must name a level, evidence and
  the revision it belongs to. Stale evidence does not satisfy a gate.
- **Capability evidence.** A declaration is not an observation, an observation
  is not an execution, and only the matching evidence level answers a claim.
- **Review independence at the engine level.** A review binds the implementing
  execution and the reviewing execution separately, and the engine refuses a
  self-review.
- **Bounded decision contracts.** A decision is confined to a declared option
  set, records its provider, model, policy version and confidence provenance,
  and can never authorize a protected action.
- **Migration honesty.** Migration is additive, preserves the original bytes,
  creates no approval, and refuses when it cannot be safe.
- **Release honesty.** The release gate fails when versions disagree, when an
  artifact does not match its manifest, when an experiment would become default,
  or when an artifact contains maintainer-only material.

## What Ariadne does not guarantee

- **No OS sandbox.** Commands run with your user's operating-system permissions.
  A validation command is executed, not jailed.
- **No cryptographic attestation of local run-state files.** Digests detect
  accidental change and are recorded as evidence; a local attacker with write
  access is outside the threat model.
- **No protection from a malicious process.** A provider or worker running on
  your machine can do anything your account can do.
- **No truth about unavailable provider observations.** If a provider does not
  report usage, identity or outcome, Ariadne records `unknown`; it cannot
  discover the truth.
- **No authority from external sources.** Text fetched or pasted from elsewhere
  is data. It cannot grant a gate, widen a scope or change policy.
- **No immunity to prompt injection.** Ariadne keeps instruction sources
  separate from data and never treats quoted text as permission, but a model
  reading adversarial content can still be manipulated within its own
  authority; the engine limits the blast radius, it does not eliminate it.
- **No model-quality guarantee.** Recorded byte or turn reductions are not
  claims about output quality. The AR-204 optimizations stay opt-in until a
  measured comparison exists.
- **No live decision-provider evidence.** The Decision Plane is exercised with
  deterministic offline providers. No live decision provider, calibration data
  or live Jev evaluation was executed, so no provider-quality claim exists.
- **No signed artifacts.** Release artifacts are authenticated by SHA-256 digest
  and by the manifest embedded in the runtime, not by a maintainer signing key.
  Signing and pinning are not implemented.
- **No cross-platform clean-install proof.** The isolated wheel installation was
  verified on one platform. Windows, macOS and Linux share the same Python entry
  point, but only the verified platform was actually executed.
- **No live Boreal integration.** Boreal was inspected read-only and its side of
  the contract is unchanged. The relationship is contract-verified, never
  live-verified.
- **No unlimited migration rollback.** Rollback is available only while the
  migrated state is unchanged. Once v2-only work exists, rollback refuses and
  the preserved pre-migration bytes stay for manual recovery.

## The trust separation

```
Decision     ≠  Authorization
Execution    ≠  Verification
Verification ≠  Acceptance
```

Each of those five things is a different record, written by a different check,
bound to a different identity. Nothing in Ariadne collapses them into one
another, and no document you can edit by hand is any of them.

## Reporting a security issue

Open a private security advisory on the repository rather than a public issue.
Include the Ariadne version (`python -m ariadne --version`), the command, and
the smallest reproduction you can build.
