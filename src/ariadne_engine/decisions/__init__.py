"""Ariadne's provider-neutral Decision Plane (AR-203 T10, expanded by AR-205D).

The Decision Plane is deliberately small and deliberately optional. It exists so
that bounded judgement — the questions whose answers can be constrained to a
closed set — is separated from both deterministic computation (which needs no
model) and generation (which is open-ended), and so that every judgement carries
the provenance needed to trust or reject it:

* :mod:`ariadne_engine.decisions.contracts` — primitives, question validation,
  the decision record shape and the confidence contract;
* :mod:`ariadne_engine.decisions.providers` — the provider interface and
  declared capabilities, a deterministic fixture, the optional provider
  boundary, and the Jev-shaped mapping adapter;
* :mod:`ariadne_engine.decisions.policy` — risk-adjusted acceptance rules. No
  confidence threshold ever grants authorization;
* :mod:`ariadne_engine.decisions.batch` — independent questions over one
  projected state, recorded as durable evidence.

AR-205D adds the execution mechanism around those primitives:

* :mod:`ariadne_engine.decisions.compiler` — classify each unresolved question
  as DETERMINISTIC, BOUNDED, GENERATIVE, HUMAN or UNRESOLVED. Code before
  judgment: a fact code already knows never becomes a model call;
* :mod:`ariadne_engine.decisions.projections` — the smallest defensible state
  projection per decision family, with REQUIRED/OPTIONAL/FORBIDDEN fields;
* :mod:`ariadne_engine.decisions.planner` — automatic batching of independent
  questions; dependent questions wait for another step;
* :mod:`ariadne_engine.decisions.graph` — a small decision dependency graph
  with cycle refusal, invalidation and a protected human boundary;
* :mod:`ariadne_engine.decisions.cache` — state/question/provider/model/policy
  bound decision reuse with structured invalidation;
* :mod:`ariadne_engine.decisions.escalation` — the structured escalation ladder
  and its declared reasons;
* :mod:`ariadne_engine.decisions.consensus` — optional independent second
  decisions; agreement is never treated as proof;
* :mod:`ariadne_engine.decisions.generation` — the generation gate: why
  generative execution was justified;
* :mod:`ariadne_engine.decisions.integrations` — the real engine paths that use
  bounded decisions;
* :mod:`ariadne_engine.decisions.trace` — the record-derived decision trace;
* :mod:`ariadne_engine.decisions.calibration` — raw outcome collection for a
  future, deliberate calibration step (no self-tuning);
* :mod:`ariadne_engine.decisions.economics` — structural decision economics.

Nothing here requires a paid service, a network call or a third-party
dependency; with no provider configured, every decision path reports
``unavailable`` and the deterministic fallback runs.
"""

from __future__ import annotations

from . import (  # noqa: F401
    batch,
    cache,
    calibration,
    compiler,
    consensus,
    contracts,
    economics,
    escalation,
    generation,
    graph,
    integrations,
    planner,
    policy,
    projections,
    providers,
    trace,
)

__all__ = [
    "batch",
    "cache",
    "calibration",
    "compiler",
    "consensus",
    "contracts",
    "economics",
    "escalation",
    "generation",
    "graph",
    "integrations",
    "planner",
    "policy",
    "projections",
    "providers",
    "trace",
]
