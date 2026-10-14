# SKILL: performance-investigation

**Trigger** — a request names speed, latency, memory, bundle size, or another measurable resource as the problem.
**Owner** — the worker making the change
**Inputs** — a runnable workload or observable path, shell access, the declared validation commands
**Output** — a baseline measurement, the hypothesis it produced, the change made, and the same measurement taken again

An optimisation without a before and after is a preference with extra steps. This
method forces the number to exist before the change and to be re-taken after it.

## Method

1. **Establish the baseline first.** Run the slow path and record the number, the
   command that produced it, and the environment. A baseline from a different
   machine or revision explains differences that are not the change.
2. **Make the cost visible before theorising.** Profile, trace, instrument, or
   bisect. The question is not "what is usually slow" but "where did this workload
   actually spend its time on this revision".
3. **Write the hypothesis as one sentence with a mechanism.** "The export re-sorts
   the full list on every row because the comparator closes over the catalogue" —
   falsifiable, and it names where to look when the measurement disagrees.
4. **Change one thing.** The hypothesis earned one change. Multiple simultaneous
   optimisations make the measurement unreadable even when the total improves.
5. **Measure again with the same command.** Same workload, same environment, same
   metric. Report the pair, not a percentage computed from memory.
6. **Guard the gain.** Where the project's tooling allows, bind the improved
   behaviour to a check (a budget assertion, a large-input test). An improvement
   nobody measures again is a temporary state.
7. **Report honestly.** A change that did not improve the metric is a finding about
   the hypothesis; revert or keep it for other reasons, but never call it a gain.

## Recording

Baseline command and number, hypothesis, the change, after number, the delta, and
any secondary cost (memory traded for latency, code size traded for speed) with its
own measurement. Unmeasured secondary effects are recorded as unmeasured.

## Stop conditions

- No workload can be run: record the blocker; do not optimise by reading alone.
- The measurement is dominated by noise: record the variance and either increase
  the sample or abandon the claim of a change.
- Reaching the target needs a new dependency or a paid service: stop; that gate is
  human-owned.
- The fix would change observable behaviour: it is a feature decision wearing a
  performance label; raise it rather than shipping it silently.
