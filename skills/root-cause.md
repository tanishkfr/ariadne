# SKILL: root-cause

**Trigger** — a defect, crash, regression, or wrong output is reported and a change is about to be made.
**Owner** — the worker implementing the fix; the orchestrator when the investigation is read-only
**Inputs** — the failure report or symptom, reproduction access, the affected code paths
**Output** — a recorded reproduction, the traced cause with its file anchor, and the smallest fix that addresses it

An unverified cause is a hypothesis, not a finding. The method below is what turns
one into the other. This skill produces evidence for the repair; it cannot approve
a gate, waive validation, or accept its own fix as verified.

## Method

1. **Reproduce before touching anything.** Get the reported failure to happen on the
   current revision and record the exact command or steps and the observed result.
   A defect that cannot be reproduced is an investigation with a missing tool, not a
   licence to change code and hope.
2. **Read the failure, do not pattern-match it.** Take the actual message, stack
   trace, log line, or diff of expected versus observed values. Quote it in the
   record. A remembered cause is not this cause.
3. **Trace backwards, one hop at a time.** From the failure point, follow the value
   or control that produced it to where it was set. Each hop names a file and line.
   Stop when you reach the decision or transformation that is wrong; that is the
   cause. The first plausible-looking line is usually a courier, not the culprit.
4. **State the cause as a mechanism.** "X is wrong because Y receives Z and treats
   it as W" — falsifiable, testable, and small enough to disprove. If the statement
   needs "and also", there are two defects.
5. **Confirm before fixing.** Make the smallest change that neutralises the cause
   and confirm the reproduction now behaves correctly. If the fix works without the
   cause being neutralised, the cause was misidentified.
6. **Bind the fix to the defect.** Leave behind a check that fails without the fix
   where the project's test setup allows it; see the [behavior-tests](behavior-tests.md)
   method. Record the residual uncertainty honestly.

## Recording

The finding survives the session only as a record. Write the reproduction, the
quoted failure, the traced hops, the cause statement with its file anchor, and the
confirmation result. A summary that says "fixed the crash" is a claim, not evidence.

## Stop conditions

- Cannot reproduce: record the attempt and the environmental blocker; ask for one
  concrete reproduction instead of editing.
- The trace leaves the repository or needs credentials you do not have: stop and
  report the boundary.
- The cause is in a sensitive subsystem: report it and stop for the applicable
  authorization rather than changing it silently.
- Two causes are plausible and the evidence does not separate them: present both
  with what would distinguish them; do not average them into one fix.
