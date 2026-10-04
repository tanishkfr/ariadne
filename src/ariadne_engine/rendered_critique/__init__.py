"""Grounded rendered critique and bounded refinement (AR-222).

AR-221 proved the code came from the right evidence. AR-222 proves the thing that
actually rendered matches the direction that was approved.

The chain it closes::

    Requirement
        -> Project identity
        -> Design references
        -> Grounded principles
        -> Approved direction
        -> Implementation plan
        -> Code
        -> Mechanical validation
        -> REAL RENDER            <-- this package
        -> Independent critique
        -> Bounded refinement
        -> RE-RENDER
        -> Rendered evidence

Nothing here is a second visual QA system. AR-202D's :mod:`ariadne_engine.render`
already defined the capture record, the evidence ladder, the capture manifest, digest
re-verification and staleness; AR-221's :mod:`ariadne_engine.critique` already defined
independent design critique, evidence-bound findings and bounded refinement. This
package extends both and adds the four things that were genuinely missing:

* a **bounded capture plan** -- what to render and why, with capture economics, because
  the alternative is a screenshot matrix nobody reads (:mod:`plan`)
* a **real rendering capability** behind a vendor-neutral contract, with no silent
  fallback to source inspection (:mod:`adapter`)
* **exact source binding** so a capture can be shown to describe the implementation it
  claims to, including for a dirty worktree (:mod:`source`)
* **independent critique and bounded repair** where the worker that made the change
  cannot close its own finding (:mod:`critique`, :mod:`refinement`)

The boundaries are the ones AR-220 and AR-221 established, and they are not weakened
here::

    reference            != authority
    observation          != recommendation
    recommendation       != approval
    constraint consulted != constraint satisfied
    source implementation != rendered correctness
    mechanical evidence   != rendered evidence != review evidence
    reference alignment   != pixel similarity

The three evidence kinds in that last line are the load-bearing addition. Mechanical
evidence (build, typecheck, tests) proves code compiles. Rendered evidence (a real
capture bound to an exact source digest) proves what appeared. Review evidence (an
independent critique of those captures) says whether it satisfies the approved
direction. None of the three may impersonate another, and the most important
consequence is negative: a green build cannot answer a design question, and this
package refuses to pretend otherwise.
"""

from __future__ import annotations

from . import adapter, contracts_bridge, critique, evidence, plan, refinement, safety, source, trace

__all__ = [
    "adapter",
    "contracts_bridge",
    "critique",
    "evidence",
    "plan",
    "refinement",
    "safety",
    "source",
    "trace",
]
