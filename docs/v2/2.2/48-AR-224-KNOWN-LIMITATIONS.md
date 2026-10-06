# AR-224 Known Limitations (public)

- Not an OS sandbox.
- A passing receipt covers the declared requirements only; undeclared
  behavior was never examined and stays unproven.
- Subjective requirements may require human judgment (NEEDS_HUMAN).
- External design providers change or disappear; project evidence stays primary.
- Some providers remain browser-only or disabled; the registry says which.
- FAILURE_CLASSIFICATION and EVIDENCE_RELEVANCE remain EVALUATED unless
  fresh AR-223-compatible evidence genuinely changes that.
- The reference-runtime benchmark is not a frontier-model benchmark.
- No hosted Proof service unless actually built.
- ChatGPT integration is integration-ready, not marketplace-published.
- Boreal integration status is consumer-conformance only; Boreal untouched.
- Cryptographic attestation state is reported in the release manifest;
  a hash is never called a signature.
- Prompt injection remains bounded by authority, not magically eliminated.
- No macOS install or smoke was run for this candidate; the wheel is
  platform-neutral pure Python, which narrows but never closes that gap.
