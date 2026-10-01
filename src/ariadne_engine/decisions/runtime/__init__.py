"""Ariadne's native Decision Runtime (AR-206).

The middle layer of Ariadne's intelligence ladder, made real:

    deterministic computation  ->  bounded local decision  ->  generation

Ariadne 2.0 already had the shape of this — a Decision Compiler that classifies each
unresolved requirement, a bounded Decision Plane that batches independent questions
over a small projected state, policy that judges, and a structured escalation ladder.
What it did not have was a bounded implementation that ships with the product. With
no provider configured, every decision path reported ``unavailable``.

This package supplies one. It is deliberately narrow:

* :mod:`~ariadne_engine.decisions.runtime.manifest` — what an installation is, and
  whether its bytes match a reviewed digest record;
* :mod:`~ariadne_engine.decisions.runtime.transport` — how Ariadne reaches a bounded
  engine without importing its dependencies, which is what keeps PyTorch and friends
  out of ``pip install ariadne``;
* :mod:`~ariadne_engine.decisions.runtime.reference` — the reference bounded engine:
  a small, real, local probabilistic classifier with no dependency at all;
* :mod:`~ariadne_engine.decisions.runtime.seeds` — first weights, derived from
  Ariadne's own deterministic tables so bounded inference works on a fresh install;
* :mod:`~ariadne_engine.decisions.runtime.session` — the narrow runtime API and the
  capability state a user sees;
* :mod:`~ariadne_engine.decisions.runtime.provider` — the adapter into the existing
  Decision Plane;
* :mod:`~ariadne_engine.decisions.runtime.profiles` — the only licence for calling a
  probability calibrated;
* :mod:`~ariadne_engine.decisions.runtime.shadow` — prediction with no execution
  effect, and the comparison that makes adoption evidence-based;
* :mod:`~ariadne_engine.decisions.runtime.promotion` — scoped, reversible adoption;
* :mod:`~ariadne_engine.decisions.runtime.evaluation` — identity-bound evaluation and
  the comparability gate;
* :mod:`~ariadne_engine.decisions.runtime.schema` — a safe subset of JSON Schema
  compiled into Ariadne primitives;
* :mod:`~ariadne_engine.decisions.runtime.shortlist` — deterministic narrowing before
  a large candidate set becomes a question;
* :mod:`~ariadne_engine.decisions.runtime.export` — the labelled-dataset export that
  a future fine-tuning path would consume;
* :mod:`~ariadne_engine.decisions.runtime.selection` — how Ariadne chooses its own
  bounded implementation, with no provider picker anywhere in the product.

The invariants this package holds, in one place, so they can be read rather than
inferred:

``decision != authorization``
    Nothing here produces an approval, a permission or a release. Every record
    carries ``authorization_effect: "none"``, and the engine contract validator
    refuses any that does not.

``decision != verification``
    A prediction selects a path. Only verification establishes an outcome.

``unknown stays unknown``
    No weights means an abstention, not a guess. No ground truth means ``UNKNOWN``,
    not a loss. No calibration profile means ``PROVIDER_PROBABILITY``, not calibrated.

``shadow cannot act``
    Shadow records are written after the authoritative decision and read by nothing
    that makes one.

None of this requires a network call, a paid service or a third-party dependency. The
reference engine is pure standard library, so the Decision Runtime is genuinely
baked in rather than merely installable.

:mod:`~ariadne_engine.decisions.runtime.sidecar` holds the executable itself. It is
deliberately not imported here: the transport launches it by file path, and importing
an entry point into the package would put ``argparse`` and a ``main`` on the import
path of every Ariadne process.
"""

from __future__ import annotations

from . import (  # noqa: F401
    evaluation,
    export,
    integrity,
    manifest,
    observe,
    profiles,
    promotion,
    provider,
    reference,
    schema,
    seeds,
    selection,
    session,
    shadow,
    shortlist,
    transport,
)

__all__ = [
    "evaluation",
    "export",
    "integrity",
    "manifest",
    "observe",
    "profiles",
    "promotion",
    "provider",
    "reference",
    "schema",
    "seeds",
    "selection",
    "session",
    "shadow",
    "shortlist",
    "transport",
]