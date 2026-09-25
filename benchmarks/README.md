# Ariadne deterministic benchmark

295 registered cases across 50 groups (AR-200 through AR-205D). Offline, no model calls, no network, no paid evaluation. The full suite reports 0 fail and 0 error; `OBSERVED` and `DECLARED_SKIP` are separate categories, never passes.

```
python benchmarks/run_benchmarks.py --list                        # list cases
python benchmarks/run_benchmarks.py                               # run every executable case
python benchmarks/run_benchmarks.py --release                     # the curated release gate
python benchmarks/run_benchmarks.py --only security               # one group
python benchmarks/run_benchmarks.py --case lifecycle.s5-isolation # one case
python benchmarks/run_benchmarks.py --write-manifest              # regenerate manifest.json
python benchmarks/run_benchmarks.py --work-root D:\tmp\ar-bench --keep-sandbox
```

The exhaustive suite is the authority. `--release` selects `arbench/release_subset.py`:
a curated subset that still covers every critical invariant area (repository and
distribution suites, lifecycle, authorization, migration, routing, recovery,
design intelligence, verification, decision plane, economics safety and the
golden workflows) and is fast enough to run as a release gate.

## Layout

| Path | Purpose |
|---|---|
| `run_benchmarks.py` | Entry point. Selects cases, runs them, prints a table, writes a results document. |
| `arbench/driver.py` | Sandboxed subprocess driver (`Repo`, `Sandbox`) for the real runtime; module loader for read-only helpers. |
| `arbench/fixtures.py` | Fixture documents; the handoff/return/review fixtures are taken from the runtime's own generators. |
| `arbench/cases.py` | The registered cases, their expectations and their evidence requirements. |
| `arbench/adaptive_cases.py` | The AR-202 adaptive-execution cases (context, routing, execution identity, recovery, continuation evidence). |
| `arbench/design_cases.py` | The AR-202D design-intelligence cases (characterisation, reference provenance, direction, rendered evidence, critique, refinement). |
| `arbench/ar203_cases.py` | The AR-203 verification-hardening and decision-plane cases (execution provenance, capability registry, review independence, render/reference verification, decision plane, false acceptance). |
| `arbench/ar204_cases.py` | The AR-204 harness-economics cases (accounting, request rendering, tool schemas, externalized output, context economics, compaction, orchestration economics). |
| `arbench/ar205_cases.py` | The AR-205 release-engineering cases (release metadata, distribution integrity, migration, the consumer contract, the six golden workflows). |
| `arbench/release_subset.py` | The curated release-gate case list. |
| `manifest.json` | Generated, machine-readable case manifest (id, task, inputs, expected outcome, evaluation method, environment/provider requirements, cost, executable, layer). |
| `results/*.json` | One document per run; `LATEST.json` mirrors the most recent. |

## Guarantees

- **Isolation.** Fixtures are created under `--work-root` (default `%TEMP%\ariadne-bench-<random>`, deleted unless `--keep-sandbox`). Nothing is written inside a repository by the harness. The runtime's own self-tests create and remove their transient workspaces under `validation/` inside the repository, as they always have.
- **Fidelity.** Cases drive the real CLI in a subprocess (`python scripts/ariadne.py …`), not internal functions, except where a case explicitly reads a helper to verify an artifact (and then the path is recorded).
- **Honest verdicts.** `pass` / `fail` measure the case's integrity expectation. `observed` records a measurement with no judgement. `error` means the harness could not evaluate. `skip` means the case declared itself not executable here — never a pass.
- **No fabrication.** `model_calls` is 0 by construction; token usage is reported as `UNKNOWN`; cost is 0.0 because no provider is invoked.

## Status vocabulary in results

```
pass      the runtime satisfied the integrity expectation
fail      the runtime violated the integrity expectation (a real defect)
observed  measurement recorded, no pass/fail judgement
error     harness failure (traceback recorded in the result)
skip      declared not executable in this environment (reason recorded)
```

## Adding a case

```python
@case(id="group.name", group="lifecycle", title="…", task="…",
      expectation="…", evaluation="…", evidence_required="…", layer="deterministic-lifecycle")
def my_case(ctx: Ctx) -> Outcome:
    box = ctx.sandbox()                     # isolated project + run root
    result = ctx.repo.cli("status", "--run-root", str(box.run_root))
    return Outcome("pass" | "fail" | "observed" | "error" | "skip", "actual", evidence={}, metrics={})
```

Then run `--write-manifest` so `manifest.json` stays generated from the registry, and confirm the case can fail before trusting it (see `scripts/validate.py --self-test` for the same discipline applied to the runtime's own guards).

## Interpreting results

See `docs/v2/AR-200/06-BENCHMARKS.md` §5. In short: a `fail` is a finding about the runtime with a reproduction inside the result document; `observed` is not a quality signal; this benchmark proves deterministic mechanics, not output quality, cost or success rate.
