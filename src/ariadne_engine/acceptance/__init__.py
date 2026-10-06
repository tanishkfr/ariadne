"""Acceptance intelligence: deciding which parts of a claimed completion are established.

AR-222 collected and preserved trustworthy evidence. AR-223 asks the harder question:

    **which parts of a worker's claimed completion are actually established by the
    evidence that exists right now?**

The gap between the two is the claim-evidence gap, and it has four edges that a system
either separates or gets wrong:

    a claim is not evidence
    missing evidence is not failure
    a passing check for one requirement says nothing about unrelated requirements
    worker-produced evidence does not automatically become independent acceptance

The model, conceptually:

    TASK
     └─ CONTRACT                    a versioned interpretation bound to the exact request
         ├─ REQUIREMENTS            independently verifiable obligations, stable ids
         ├─ CLAIMS                  what workers say they did -- never evidence
         ├─ EVIDENCE                what was observed, by whom, about which revision
         └─ VERIFICATION DECISIONS   one of six verdicts per requirement, per pass
                  ↓
             ACCEPTANCE STATE       explicit, countable, never a percentage

Six modules, in dependency order:

:mod:`~ariadne_engine.acceptance.contract`
    the request, bound to its digest, versioned, and un-rewritable
:mod:`~ariadne_engine.acceptance.requirements`
    the obligations, their provenance, and their requirement-specific evidence policies
:mod:`~ariadne_engine.acceptance.claims`
    what was said, who said it, about which revision, and never mistaken for proof
:mod:`~ariadne_engine.acceptance.evidence`
    what was observed, whose it is, whether it is still current, and where it disagrees
:mod:`~ariadne_engine.acceptance.decisions`
    the six verdicts, with their exact semantics and their derivation
:mod:`~ariadne_engine.acceptance.gates`
    the only place acceptance is decided, and the only place it is explained

plus :mod:`~ariadne_engine.acceptance.invalidation` for selective re-verification,
:mod:`~ariadne_engine.acceptance.security` for what an outside party can put in a claim,
and :mod:`~ariadne_engine.acceptance.integrations` for joining all of it to the records
AR-220 to AR-222 already wrote.

The six verdicts, and the two separations that matter most:

    PROVEN         current evidence, sufficient under this requirement's own policy
    PARTIAL        a meaningful subset is established and the rest is outstanding
    UNPROVEN       nothing contradicts it and sufficient evidence is missing
    FAILED         current evidence observes it being violated
    NEEDS_HUMAN    the evidence cannot honestly support an automatic decision
    CONTRADICTED   not a requirement verdict: a worker's claim the evidence disproves

    UNPROVEN  != FAILED
    FAILED    != CONTRADICTED

AR-224 turns this into a public Proof Pass. This package is the engine underneath it, and
deliberately exposes no receipt formatting.
"""

from __future__ import annotations

from . import (
    claims,
    contract,
    decisions,
    evidence,
    gates,
    integrations,
    invalidation,
    requirements,
    security,
)
from .. import contracts as _contracts

VERSION = "ar-223-acceptance-1"
"""The acceptance package version."""

VERDICTS = _contracts.ACCEPTANCE_VERDICTS
"""The stable verdict vocabulary, re-exported so one import answers everything."""

__all__ = [
    "VERDICTS",
    "VERSION",
    "claims",
    "contract",
    "decisions",
    "evidence",
    "gates",
    "integrations",
    "invalidation",
    "policy",
    "requirements",
    "security",
]