# AR-224R Release Evidence

Measured on branch `v2/2.2-ar224-proof-pass` against RC source `d5ab42c`
(`dist/` artifacts built from that commit; runtime source untouched since).
Nothing in this file is copied from an earlier report without re-running.

## AR-221 fixture restoration

The AR-221 vertical slice needs the committed `desktop-tool` lockfile
materialised. A fresh worktree has no `node_modules` (ignored, untracked),
so the slice exhausted its repair budget on a missing toolchain. Running
`npm ci --no-audit --no-fund` inside
`src/ariadne_engine/design_execution/fixtures/desktop-tool` added 3
packages from the lockfile in 2 seconds. Tracked tree unchanged.

## AR-221 re-run

`scripts/test-design-execution.py`: 68/68 green, including the real slice
reaching mechanical validation. The earlier 67/68 was a missing
`node_modules`, reproduced on pristine base `f0affa6`, environmental rather
than a source defect. No source fix was required, so the RC source stands.

## Omitted suite results

- AR-221 adversarial: 35/35 held.
- AR-221 mutations: 25/25 caught.
- AR-220 reference mutations: 22/22 caught (functional 109/109 held).
- AR-222 critique adversarial: 27/27 held (functional 87/87 held).
- AR-222 critique mutations: 40/40 caught; ledger idle and tree clean after.
- AR-222D mutations: 35/35 caught.
- Decision mutations: 9/9 caught; engine sources byte-identical after.
- Benchmarks curated release gate: 89 pass, 0 fail, 0 observed, 0 error,
  0 skipped in 186 seconds; record
  `benchmarks/results/ar-205-release-20261006T162752.json` (ignored run
  record, not a tracked artefact).

Two harness runs were killed by the surrounding tool environment
mid-mutation (M18 and M26/M29). Both left the shared ledger entries that
later runs detect; one recovered transactionally from its stash, the other
needed `git checkout` of a single AR-222 file last committed before
AR-224. Ledger reads `[]` and the tracked tree is clean after each event.

## Packaged F1 Design Specificity

The RC runtime zip was extracted to a scratch directory and the F1 slice
(`design_reference.specificity.vertical_slice.run`) executed from the
packaged bytes with the vague request and no aesthetic guidance. 29 of 29
gates held: content model first across 3 surfaces with derived layout
constraints and no filler, 3 candidates across 3 families with an empty
divergence-problem list, per-concept failure modes and richness sources,
150 skipped-with-reason selections with 14 of 39 sources queried,
4 detected defaults with 4 earned and kept, an actionable unexamined
list, motion intents with evidence, the workstation recommendation,
zero leaked internal fields, zero platform leaks, human G1D authority
binding the shown text, zero interruptions after approval, slice
completed with no failures, one recommendation, plan continuation, no
global score, no house style, house method present. A live Chromium
render of the dashboard was not run here; the offline method slice is
what the package run proves.

## Installed MCP transport

Against the same extracted RC tree with a four-verb fixture connector:
3 default adapters report honest unavailability with inert search, the
fixture advertises exactly the 4 transport verbs, search returns tagged
data, no approve verb exists, and undeclared capabilities are refused.
12 of 12 gates held. Authority stays engine-side.

## Linux clean install and smoke

Real Linux: WSL2 Ubuntu, kernel 6.18.33.2-microsoft-standard-WSL2 x86_64,
Python 3.14.4. After user-local pip bootstrap, the RC wheel installed
from its release path and `python -m ariadne --version` printed 2.2.0rc1.
`install` plus `doctor` reported healthy (absent Codex/Claude CLIs noted
as informational; Decision Runtime optional and absent). The installed
runtime's own controller verified a temp project end to end: VP-0001 with
requirement detail, VP-0002 on a second digest, and a three-line
comparison. Installed wheel digest matches the release manifest
(`c47af00f...4159`), so the Linux-tested bytes are the manifested bytes.

## macOS

No macOS hardware, virtual machine, or Mac CI runner exists in this
environment, and none was provisioned during this run, so no macOS
install or smoke was executed. The wheel is platform-neutral pure Python
(`py3-none-any`, standard library only) and the macOS data-home branch is
covered by the distribution path tests; that bounds but does not replace
a real Mac run. The limitation stays in the public known limitations.

## Signing

No keyless attestation or signing facility exists here, no private key
was created or committed, and no secret was introduced. Digests plus the
embedded manifest remain the integrity mechanism, explicitly not
signatures.

## Publication

No tag was created and nothing was uploaded. `v2.2.0rc1` and `v2.2.0`
remain uncreated; `dist/` holds local candidate bytes only.

## Source-defect verdict

Every gap closed above traced to environment or evidence handling
(missing fixture packages, tool-killed harnesses, unprovisioned macOS),
never to engine semantics. No runtime source file changed for AR-224R,
so `d5ab42c` stays the RC source and no rebuild was required.
