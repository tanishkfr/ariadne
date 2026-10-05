"""Verified intelligence: proving that a bounded engine deserves the authority it is given.

AR-206 built the Native Decision Runtime and its adoption machinery. What it could not do was
show that the reference engine is *good*, because nothing had ever measured it against
reviewed labels. This package is that measurement, and the small amount of policy that follows
from it:

    corpus.py      the splits, the leakage guards, and what a corpus must declare
    corpus_data.py several hundred reviewed labels, with reviewers and disagreements
    evaluation.py  the real engine over the real corpus, per family, with the 2.1
                   false-confidence pathology looked for directly
    calibration.py thresholds and temperatures fitted on development only, bound to a
                   six-dimensional identity that invalidates them when it moves
    promotion.py   measured merit as the second gate to authority, and the only automatic
                   removal of it
    scheduler.py   the cheapest intelligence that has earned enough quality for this decision

**The principle underneath all six.**

    A bounded engine that has not been measured may not answer, however good it looks.
    A bounded engine that has been measured badly may not answer either, however good it
    looks. And no measurement of any engine may grant permission: quality evidence and
    authorization are different quantities with different owners, and this package keeps
    them apart at the one place where they touch.

The honest outcome of running this against the shipped engine is in
``docs/v2/2.2/34-AR-223-RESULTS.md``, including which families earned ``ACTIVE`` and which
did not.
"""

from __future__ import annotations

from . import calibration, corpus, corpus_data, evaluation, promotion, scheduler
from .calibration import CALIBRATION_VERSION, IDENTITY_KEYS, fit, stale_reasons
from .corpus import (
    CORPUS_VERSION,
    EVALUATION_SPLITS,
    FAMILIES,
    SPLITS,
    leakage_problems,
    require_clean,
)
from .corpus_data import corpus as authored_corpus
from .evaluation import EVALUATION_VERSION, degradation, evaluate, sweep
from .promotion import POLICY as PROMOTION_POLICY
from .promotion import PROMOTION_VERSION, assess, enforce_health, promote
from .scheduler import LEVELS, PROTECTED_OPERATIONS, SCHEDULER_VERSION, choose

__all__ = [
    "CALIBRATION_VERSION",
    "CORPUS_VERSION",
    "EVALUATION_SPLITS",
    "EVALUATION_VERSION",
    "FAMILIES",
    "IDENTITY_KEYS",
    "LEVELS",
    "PROMOTION_POLICY",
    "PROMOTION_VERSION",
    "PROTECTED_OPERATIONS",
    "SCHEDULER_VERSION",
    "SPLITS",
    "assess",
    "authored_corpus",
    "calibration",
    "choose",
    "corpus",
    "corpus_data",
    "degradation",
    "enforce_health",
    "evaluate",
    "evaluation",
    "fit",
    "leakage_problems",
    "promote",
    "promotion",
    "require_clean",
    "scheduler",
    "stale_reasons",
    "sweep",
]