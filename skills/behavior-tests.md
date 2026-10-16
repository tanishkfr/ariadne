# SKILL: behavior-tests

**Trigger** — a defect fix, feature, or refactor can be expressed as a behaviour the project's own tooling can run.
**Owner** — the worker implementing the change
**Inputs** — the required behaviour (from the task contract or the defect), the project's test runner, write access inside the permitted scope
**Output** — an executable check that distinguishes correct from incorrect behaviour, or a recorded reason no such check exists

Tests are taken here as a design instrument, not a ritual. The test states what
"correct" means before the implementation decides it.

## Method

1. **Express the behaviour, not the implementation.** Write the check against what
   an observer can see: inputs, outputs, state transitions, error cases. A test
   that mirrors internal calls breaks when the internals are improved.
2. **Make it fail first, for the right reason.** Run it against the current
   revision. For a defect, it must fail with the defect's failure; a test that
   fails with an unrelated error has not captured the defect.
3. **Make the smallest change that passes it.** Implementation follows the check.
   If passing the check requires unrelated changes, the check is too large or the
   scope was wrong; return to the task contract.
4. **Cover the edges the behaviour names.** Empty, missing, present-but-wrong,
   boundary values, and the error contract. One test per claim; no test proves a
   category.
5. **Keep the check honest.** No sleeps that hide races, no assertions that pass
   on any output, no testing the mock. If the setup is more complex than the
   behaviour, the design under test needs the architecture-evaluation method first.
6. **Run the declared validation commands.** The task contract's required checks
   are the ones the engine reruns; a green local test does not replace them.

## Recording

Record the check's name, the behaviour it binds, the command that runs it, and the
before/after results (fail-then-pass for a fix). "Tests pass" without the command
and the transition is a claim.

## Stop conditions

- The project has no runnable test setup: record the reason, propose the smallest
  available check (a script, a reproduction command), and say what remains unproven.
- The behaviour cannot be observed without a service, credential, or environment
  you do not have: record the blocker; do not simulate the observation.
- Passing the check requires weakening another guarantee: stop; that is an
  architecture decision, not a test decision.
