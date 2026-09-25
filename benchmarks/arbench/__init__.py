"""AR-200 deterministic benchmark harness for Ariadne.

This package drives the *real* Ariadne runtime scripts (scripts/ariadne.py,
scripts/prepare-stage.py, ...) from a sandbox located outside every repository.
It never calls a model, never touches the network, and never writes inside the
runtime repository except for the runtime's own transient self-test workspace
(which the runtime creates and removes itself).

Layers:
    driver.py         -> subprocess driver + sandbox
    fixtures.py       -> fixture documents reused from the runtime's own fixtures
    cases.py          -> the AR-200/AR-201 benchmark cases, grouped by capability
    adaptive_cases.py -> the AR-202 adaptive-execution cases (context, routing,
                         execution identity, recovery, continuation evidence)
    design_cases.py   -> the AR-202D design-intelligence cases (characterisation,
                         reference provenance and adapters, component intelligence,
                         design direction, requirement closure, rendered evidence,
                         independent critique, bounded refinement, trust invariants)
    ar203_cases.py    -> the AR-203 verification-hardening and decision-plane cases
                         (execution provenance, capability registry, review
                         independence, render/reference verification, the bounded
                         decision plane, false-acceptance attacks)
    ar204_cases.py    -> the AR-204 harness-economics cases (task-level accounting,
                         request rendering, tool schemas, output externalization,
                         context economics, compaction, decision economics,
                         orchestration economics)
    ar205d_cases.py   -> the AR-205D decision-intelligence cases (compiler
                         classification, decision graph semantics, automatic
                         batching, projection-bound cache, escalation ladder,
                         real integrations, structural economics, golden
                         decision workflows)
"""

from . import cases  # noqa: F401  (registers the AR-200/AR-201 cases)
from . import adaptive_cases  # noqa: F401  (registers the AR-202 cases)
from . import design_cases  # noqa: F401  (registers the AR-202D cases)
from . import ar203_cases  # noqa: F401  (registers the AR-203 cases)
from . import ar204_cases  # noqa: F401  (registers the AR-204 cases)
from . import ar204_measure_cases  # noqa: F401  (registers the AR-204 measurement cases)
from . import ar205_cases  # noqa: F401  (registers the AR-205 release-engineering cases)
from . import ar205d_cases  # noqa: F401  (registers the AR-205D decision-intelligence cases)
