# AR-205 — 07 — Release tests, gate and regression record

## The release gate

```bash
python scripts/release-check.py
```

One local command runs and reports, with the AR-205 vocabulary
(`PASS`, `FAIL`, `OBSERVED`, `DECLARED_SKIP`, `NOT_EXECUTED`, `BLOCKED`):

| Check | What it runs |
|---|---|
| clean worktree | `git status --porcelain` |
| version consistency | `ariadne_engine.release.version_problems` |
| public API surface | `ariadne_engine.release.public_surface_problems` + import test |
| experimental defaults | `ariadne_engine.release.experimental_defaults_problems` |
| repository contract | `scripts/check.py` |
| release tests | `scripts/test-release.py` |
| distribution lifecycle | `scripts/test-distribution.py` |
| runtime bundle and private material | `scripts/build-release.py --self-test` |
| release benchmark subset | `benchmarks/run_benchmarks.py --release` |
| wheel install | `scripts/test-wheel-install.py` |
| release artifacts | `ariadne_engine.release.artifact_problems --dist` |

A `FAIL` exits `1`. Skipped checks stay visible; nothing is silently upgraded to
`PASS`. `--allow-dirty` turns the clean-tree check into `OBSERVED` for
development runs and is not used for the recorded candidate.

## Clean install / update / rollback matrix

| Row | How it is tested | Result |
|---|---|---|
| fresh v2 install | `scripts/test-wheel-install.py` (build wheel, venv, install, `doctor`) | PASS 14/14 |
| built candidate wheel in isolation | the `dist/ariadne-2.0.0rc1-py3-none-any.whl` artifact installed into a throwaway venv; `--version`, `install`, `doctor` and a project start from the installed runtime outside any checkout | PASS |
| v1 installed → install v2 | `scripts/test-distribution.py` update chain over synthetic bundles | PASS (in 55/55) |
| v1 project opened in v2 without migration | `lifecycle.schema-migration-explicit`; release suite `plan` cases | PASS — refused until explicit |
| v1 project migrated to v2 | release suite migration cases; `golden-workflows.migration-cli` | PASS |
| v2 → reinstall same version | `test-distribution.py` repair/reinstall cases | PASS (in 55/55) |
| v2 → rollback runtime | `test-distribution.py` rollback cases | PASS (in 55/55) |
| v2 migrated project → migration rollback | release suite `migration.rollback-*`; `migration.rollback-refuses-after-v2-work` | PASS, with the refusal documented |

## Suite results at the release candidate

| Suite | Command | Result |
|---|---|---|
| Runtime self-test | `python scripts/ariadne.py --self-test` | PASS 125/125 |
| Transport self-test | `python scripts/prepare-stage.py --self-test` | PASS 50/50 |
| Repository contract | `python scripts/check.py` | PASS |
| Contract self-test | `python scripts/check.py --self-test` | SELF-TEST PASS |
| Distribution lifecycle | `python scripts/test-distribution.py` | PASS 55/55 |
| Release tooling | `python scripts/build-release.py --self-test` | PASS 18/18 |
| Reasoners | `python scripts/reasoners.py` | PASS 15/15 |
| Real projects | `python scripts/test-real-projects.py` | PASS 29/29 |
| Social intelligence | `python scripts/test-social-intelligence.py` | PASS 68/68 |
| Validation guards | `python scripts/validate.py --self-test` | PASS 29 guards |
| Validation benchmark | `python scripts/validate.py --benchmark` | measurement run completes; no failure raised |
| Writing architecture | `python scripts/test-writing-architecture.py` | PASS 15/15 |
| Writing execution | `python scripts/test-writing-execution.py` | PASS 14/14 |
| Engine core | `python scripts/test-engine-core.py` | PASS 457/457 |
| AR-205 release tests | `python scripts/test-release.py` | PASS 81/81 |
| Wheel install | `python scripts/test-wheel-install.py` | PASS 14/14 |
| Release subset | `python benchmarks/run_benchmarks.py --release` | 45 cases, 0 fail, 0 error |
| Complete benchmark | `python benchmarks/run_benchmarks.py --label "AR-205 final exhaustive"` | 259 cases: 252 pass, 5 observed, 2 declared skip, 0 fail, 0 error, 424 s |
| Release gate | `python scripts/release-check.py --dist dist` | see `12-AR-205-REPORT.md` §19 |

All 226 AR-204 benchmark cases remain registered and pass; AR-205 adds 33 cases
(release metadata 6, distribution 4, migration 10, integration contract 7,
golden workflows 6). No case was deleted or relaxed.

The benchmark's `suite.wheel-install` case remains a **declared skip** by design:
the harness does not create a nested virtual environment. The real wheel path is
executed by `scripts/test-wheel-install.py` inside the release gate (14/14) and,
for the candidate artifact, by the isolated install recorded above.

## What the tests do not claim

- No model-quality comparison was executed; the AR-204 behavior-sensitive flags
  are asserted to stay off by default rather than promoted.
- Boreal was not present to execute; its compatibility is contract-verified
  only.
- Wheel install was executed in an isolated venv on this machine; a
  second-platform run remains part of the human handoff.
