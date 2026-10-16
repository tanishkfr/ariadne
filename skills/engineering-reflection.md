# SKILL: engineering-reflection

**Trigger** — the same failure class has been repaired more than once, or a review finding generalises beyond the single change.
**Owner** — the worker or orchestrator closing the task; the correction itself is reviewed like any other change
**Inputs** — the recorded failures, repairs, and findings for this project and task
**Output** — one durable correction bound to the repeated error: a check, a rule, or a sharpened contract

Repetition is the only reliable signal that a problem is structural. The output
here is not a retrospective essay; it is a change to something that will run
again — a test, a policy line, a template field, or a skill method.

## Method

1. **Collect the evidence first.** The failures with their classes, the repairs
   that followed, and the findings that repeated. Memory of "it keeps happening"
   is not enough; the records are what make the pattern real.
2. **Name the pattern in one sentence.** "Handler changes keep skipping the
   serialisation check" — if the sentence needs a list of unrelated incidents, the
   pattern is not found yet.
3. **Find the weakest permanent place to stop it.** Prefer, in order: a check the
   project already runs, a field the contract already has, a line in a policy the
   workflow already reads. A new document nobody opens is the weakest option and
   should be the last.
4. **Write the correction as a change, not a note.** A test that fails on the old
   behaviour, a required field that cannot be left empty, a one-line rule in the
   canonical owner. If the correction is prose, say where it will be enforced.
5. **Verify the correction would have caught the original.** Re-run the scenario
   against the new check. A correction that does not reproduce red on the old
   failure is decoration.
6. **Keep the record small.** The repeated error, the pattern, the correction, and
   where it lives. This record is evidence for the next review, not a diary.

## Recording

Failure classes with their records, the pattern sentence, the correction and its
enforcement point, and the confirmation that it catches the original case.

## Stop conditions

- The pattern is based on one incident: it is not repeated yet; record the incident
  and stop.
- The correction requires changing a canonical policy or contract outside the
  task's scope: propose the change with its evidence; a human or a later task owns
  the edit.
- No durable place exists yet (no test harness, no contract): record that gap as
  the finding — the missing enforcement point is the real defect.
