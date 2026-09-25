# 05 — Escalation

Uncertainty is escalated, never disguised. `ariadne_engine.decisions.escalation`
implements one ladder:

```
DETERMINISTIC
     | unresolved
BOUNDED DECISION
     | insufficient / low confidence
STRONGER BOUNDED DECISION
     | insufficient
GENERATIVE REASONING
     | policy requires
HUMAN
```

Not every task traverses every level, and a decision that policy accepts stops
the ladder immediately. Every escalation carries a structured reason from the
declared vocabulary rather than a vague "needs a stronger model":

| Reason | When it applies |
|---|---|
| `NO_DETERMINISTIC_RULE` | No deterministic rule exists for the requirement. |
| `NO_DECISION_PROVIDER` | The bounded mechanism has no configured provider. |
| `LOW_CONFIDENCE` | The recorded confidence came from a weak source, or the value was refused. |
| `NO_CONFIDENCE` | No confidence was recorded at all — distinct from a zero, and never treated as one. |
| `CAPABILITY_MISSING` | The configured provider does not declare the needed capability. |
| `CONFLICTING_EVIDENCE` | The evidence contradicts itself. |
| `OUT_OF_DISTRIBUTION` | The answer fell outside the declared space. |
| `DECISION_FAILED` | The provider failed. |
| `GENERATIVE_REQUIRED` | The requirement genuinely needs creation or open reasoning. |
| `POLICY_REQUIRES_HUMAN` | Policy reserves the choice to a person. |
| `INSUFFICIENT_STATE` | A required projection field was missing. |
| `DECISION_CONFLICT` | Two independent decisions disagreed. |
| `UNRESOLVED_CLASSIFICATION` | The compiler could not classify the requirement. |
| `DECISION_REFUSED` | The decision was refused without a more specific cause. |

A protected consequence always lands on `HUMAN`. When no stronger bounded
mechanism and no generative execution exist, the honest destination is the human
rung — never a silent retry, and never a plausible default.

## Stronger is not more expensive

The strengthening options are capability-shaped and deliberately unordered by
cost:

* `alternate_provider` — another configured provider that declares the primitive;
* `specialised_provider` — a provider specialised for this question family;
* `richer_projection` — the projection contract has optional fields this attempt
  did not carry;
* `alternate_question_version` — an alternative formulation of the same question;
* `independent_second_decision` — ask one independent provider and compare.

Nothing in the engine selects a provider by price, and no option carries a
monetary ordering. Price is not capability.

## Policy under the ladder

The ladder describes what *can* be done; policy decides what is *allowed*. A
decision that policy accepts as evidence does not authorize anything, and a
refusal always names the deterministic fallback or the human escalation rather
than proceeding quietly. See [09 — Security](09-SECURITY.md) for the tests that
keep confidence non-authoritative.
