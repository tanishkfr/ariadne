# Ariadne examples

Minimal, runnable examples of the public Python surface. They are deterministic
and offline: nothing here calls a model, and no paid provider is needed. Each
example uses a temporary directory and prints what it observed.

Run them from a source checkout:

```bash
python examples/01_basic_task.py
python examples/02_approval_boundary.py
python examples/03_verification_ladder.py
python examples/04_bounded_decision.py
python examples/05_recovery_inspection.py
```

| Example | Shows |
|---|---|
| 01 | start a run through the public API and read its state |
| 02 | why an approval cannot be forced, and what binds one |
| 03 | the verification ladder and an unsatisfied claim |
| 04 | a bounded decision with a deterministic provider |
| 05 | recovery inspection that reports rather than repairs |

The examples import `ariadne_engine` from `src/` and drive the same runtime the
command line uses. A real project would reach gates, reviews and design evidence
through the full workflow; the benchmark suite in `benchmarks/` covers those
end-to-end paths deterministically.
