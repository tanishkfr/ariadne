# Ariadne 2.1 - the native Decision Runtime

Ariadne 2.0 described a bounded Decision Plane and shipped no bounded
implementation with it. With no provider configured, every decision path
reported `unavailable`, the deterministic fallback ran, and the middle layer of
the intelligence ladder existed only on paper. Ariadne 2.1 supplies one: a small
on-device engine that answers Ariadne's own bounded questions - failure
classification, review escalation, evidence relevance, route family - inside a
sidecar subprocess that Ariadne never imports.

It is deliberately narrow, and it is deliberately untrusting of itself. It never
authorises anything. It is never verification. It watches a decision before it is
allowed near one. Where it cannot answer honestly it abstains with a named reason
rather than returning a plausible number. And the probabilities it reports are
labelled uncalibrated, because nothing has measured them.

Nothing in this set is a promotion advertisement. Shadow mode is the posture, and
it is the posture the shipped defaults leave you in.

## The documents

| Document | What it answers |
|---|---|
| [Overview](overview.md) | What the Decision Runtime is, the problem it solves, and the five design rules it is built on. |
| [Architecture](architecture.md) | The components, the four-method sidecar protocol, the transports, discovery and the process lifecycle. |
| [Bounded inference](bounded-inference.md) | The answer-space contract: the three supported primitives, how an Ariadne question reaches the engine, and why `MultiSelectDecision` is refused. |
| [Batching](batching.md) | One projected state and many independent questions as a single inference, the answer-slot naming, and why dependent questions stay staged. |
| [Abstention and thresholds](abstention-and-thresholds.md) | The structured refusal reasons, why no universal confidence threshold exists, and how a caller or policy supplies one. |
| [Calibration](calibration.md) | `CalibrationProfile`, the exact match set a `PROVEN` profile must satisfy, and why the runtime cannot grant itself calibration. |
| [Shadow mode](shadow-mode.md) | What is recorded beside a decided answer, what is deliberately not kept, and why `DISAGREE` is not a verdict. |
| [Promotion and scopes](promotion-and-scopes.md) | The adoption lifecycle, the transition table, the eligibility scope, and why scope is checked per call. |
| [Evaluation and comparability](evaluation-and-comparability.md) | The identity keys that bind a measurement, the metrics, and the rules under which a comparison is refused. |
| [Security model](security-model.md) | The authority boundary, the attack surface, the invariants, and how to report a suspected problem. |
| [Operations](operations.md) | Install, status, doctor, evaluation and promotion from the command line; environment variables; integrity; troubleshooting. |
| [Release closure](13-RELEASE-CLOSURE.md) | The one remaining correctness gap in 2.1, how it was wired, and what the closure pass verified. |

## Orientation

Ariadne's vocabulary for this feature is **Decision Runtime**. That is what the
status record says, what the CLI prints, and what a user is asked to understand.
Names such as `ariadne-reference-bounded` appear in diagnostics and in recorded
provenance, because provenance that cannot name its implementation is not
evidence - but they are never product branding, and there is no vendor picker and
no provider flag anywhere in the product surface.

If you are deciding whether to turn this on for your own project, read
[Overview](overview.md) and then [Shadow mode](shadow-mode.md). Those two
documents are the decision. The rest is reference.

If you are integrating against the engine, start with
[Architecture](architecture.md) and [Bounded inference](bounded-inference.md); the
rest explains why the limits are where they are.

## Verification status

The functional suite `scripts/test-decision-runtime.py` is the authority on what
the Decision Runtime does. It drives the reference engine both in-process and over
the real subprocess sidecar, so the shipping transport is exercised rather than
assumed, and it is run by the release gate (`scripts/release-check.py`, check
*engine suites*).

Its check count is growing as the feature hardens; run it rather than trusting a
number quoted here:

```bash
python scripts/test-decision-runtime.py
```

No check in it asserts model quality, latency on a particular machine, or
cross-platform behaviour. A green suite means the documented invariants hold. It
does not mean the engine is good at anything - see
[Overview](overview.md), *What is not done*.

## Related material in 2.0

The Decision Runtime completes a shape that already existed. Read alongside:

- [Decision Compiler](../AR-205D/01-DECISION-COMPILER.md) - how a requirement
  becomes a bounded question.
- [Decision Graph](../AR-205D/02-DECISION-GRAPH.md) - the execution vocabulary the
  question sits in.
- [State projections](../AR-205D/03-STATE-PROJECTIONS.md) - the projected state a
  question is answered against.
- [Providers](../AR-205D/07-PROVIDERS.md) - the interface the runtime arrives as.
- [Security of Decision Intelligence](../AR-205D/09-SECURITY.md) - the adversarial
  model the runtime inherits.
- [Trust boundaries](../../../docs/guides/TRUST.md) - what Ariadne does and does not
  guarantee.
