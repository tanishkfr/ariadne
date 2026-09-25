# AR-205 — 12 — Milestone report

## 1. Repository state

| Field | Value |
|---|---|
| Repository | `<path>` (worktrees as siblings) |
| Worktree | `<path>` |
| Branch | `v2/ar-205-release-candidate` |
| Base commit | `2e132b2a00cf67ea53cf307d7342deedd1b3e216` (AR-204 frozen) |
| Artifact release commit | `ced38012383e038e3a7bb900b029c835d7b64952` (the commits after it are documentation-only) |
| Milestone record commits | the result/gate commit and the audit commit that follow the artifact build; `git log` shows the exact HEAD |
| Remote action | none; no push, tag, release or publication |

## 2. Baseline reproduction

AR-204 at the pinned base reported 226 benchmark cases (219 pass, 5 observed,
0 fail, 0 error, 2 declared skip) and engine core 457/457. Both were reproduced
from this worktree before any change. At the candidate the complete suite holds
the same shape with 33 added cases: **259 cases, 252 pass, 5 observed, 2 declared
skip, 0 fail, 0 error** (`benchmarks/results/LATEST.json`, label
"AR-205 final exhaustive").

## 3. Public surfaces

Classified in [01-PUBLIC-SURFACES.md](01-PUBLIC-SURFACES.md). No internal module
was promoted accidentally; the release gate fails on an unclassified API export.

## 4. API and CLI

Documented in [06-RELEASE-API.md](06-RELEASE-API.md). The v1 command set, exit
codes and file formats are unchanged; `migrate` and `--version` are additive.

## 5. Migration

[02-MIGRATION.md](02-MIGRATION.md). Dry run, additive apply with a preserved
backup, durable evidence, and a rollback that refuses once v2-only work exists.

## 6. Distribution

[03-DISTRIBUTION.md](03-DISTRIBUTION.md) and
[adr/ADR-0001-distribution-name-strategy.md](adr/ADR-0001-distribution-name-strategy.md).
Local wheel, runtime bundle, descriptor and checksums; PyPI publication deferred
with an explicit warning.

## 7. Clean install

Wheel install suite 14/14 in a throwaway venv: build, install, entry point,
`python -m`, doctor, project start, uninstall. The built candidate wheel
(`dist/ariadne-2.0.0rc1-py3-none-any.whl`) was additionally installed into a
fresh venv and completed `--version`, `install`, `doctor` and a project start
from the installed runtime, with no source checkout on `sys.path`.

## 8. Versioning

`2.0.0rc1` across `VERSION`, the launcher metadata, the runtime, release notes,
install documents, the installation example and the release manifest; enforced
by `release.version_problems`.

## 9. Boreal integration contract

[04-INTEGRATION-CONTRACT.md](04-INTEGRATION-CONTRACT.md) and
[05-BOREAL-COMPATIBILITY.md](05-BOREAL-COMPATIBILITY.md). Ariadne-side adapter,
protocol version 1, capability negotiation and fixtures: `CONTRACT_VERIFIED`.
Boreal unmodified and not present; no live verification.

## 10. Provider and Decision Plane

The deterministic provider works offline; optional providers are absent by
default and produce capability state, not crashes. Decision Plane release status:
the deterministic provider and the bounded evaluation path are STABLE_V2; external
provider integration is ADAPTER_OPTIONAL and unexercised.

## 11. AR-204 experiments

All seven behavior-sensitive settings remain experimental and off by default;
`output_externalization` stays the only safe default-on setting. See
[09-EXPERIMENTAL-FEATURES.md](09-EXPERIMENTAL-FEATURES.md).

## 12. Release benchmarks and golden workflows

[07-RELEASE-TESTS.md](07-RELEASE-TESTS.md). Six golden workflows (mechanical,
protected, failure/repair, design chain, decision plane, migration) pass
end-to-end and are part of the 45-case release subset.

## 13. Full regression

[07-RELEASE-TESTS.md](07-RELEASE-TESTS.md). Every suite green: runtime 125/125,
transport 50/50, repository contract PASS, distribution 55/55, release tooling
18/18, reasoners 15/15, real projects 29/29, social 68/68, validation guards 29,
writing 15/15 and 14/14, engine core 457/457, AR-205 release tests 81/81, wheel
install 14/14, release subset 45 cases 0 fail, complete benchmark 259 cases
0 fail / 0 error. No test was weakened, skipped or deleted to reach this state.

## 14. Security and adversarial review

[08-SECURITY-AND-TRUST.md](08-SECURITY-AND-TRUST.md). One real defect found and
fixed (escalated-retry scope false positive); mutation checks for version,
artifact hash, protocol range, experimental default, manifest completeness and
unclassified exports.

## 15. Documentation

README (product entry point), `MIGRATING-v1-to-v2.md`, `TRUST.md`, examples,
release notes draft, this milestone set. Licence and dependency audit recorded in
[03-DISTRIBUTION.md](03-DISTRIBUTION.md): Apache-2.0, zero runtime dependencies,
zero third-party imports in shipped code, no bundled third-party code.

## 16. Branding

`assets/ariadne-banner.png`, `ariadne-logo.png`, `ariadne-mark.png`,
`ariadne-wordmark.png` cropped from the maintainer-supplied image and wired into
the README; vector replacements remain a human asset step.

## 17. Release candidate

Local artifacts built from release commit `ced3801` (2.0.0rc1):

| Artifact | SHA-256 |
|---|---|
| runtime zip | `86c67a2777f6da1efaba6b0c93c8e3d7505750482e07c0e2bf55e3d350c62974` |
| launcher wheel | `3e20a46d7378a2707ffe90acab5b7766d9def37a00b3afebb7006800c53c87f4` |
| release descriptor | `391460df730e8f10a1452a6199799c931881c1dfe61f6305652d358e54bc364e` |
| release notes | `fc641d1fc68957c0d242065818a3edcd37d84684e60efd91261613acacc3db66` |

`release.artifact_problems` reports no problems; the wheel was installed and
started in isolation. No tag, push, release or publication occurred.

## 18. Known limitations

- no live provider-quality comparison; no behavior-sensitive promotion;
- Boreal compatibility contract-verified only;
- no artifact signing or pinning;
- no OS sandbox or local attestation;
- migration rollback unavailable after v2-only work;
- one-platform wheel installation in this record.

## 19. Closure decision

**READY_FOR_USER_ACCEPTANCE**

The release gate run recorded before this commit (`python scripts/release-check.py
--allow-dirty --dist dist`) reported: version consistency PASS, public API PASS,
experimental defaults PASS, repository contract PASS, release tests 81/81 PASS,
distribution 55/55 PASS, release tooling 18/18 PASS, release subset 45 cases
PASS, wheel install 14/14 PASS, release artifacts PASS against `dist`, and the
clean-tree check OBSERVED because the record commit was still pending. The
definitive clean-tree gate run follows the record commit with no pending edits.

The human still decides whether to tag, publish and ship; AR-205 has prepared
the candidate and performed no public release action.
