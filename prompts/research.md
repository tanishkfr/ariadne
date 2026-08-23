# PROMPT: Conditional research (S2)

**Paste into:** a fresh reasoning session only when a fact about the world blocks S1 or S3.
**Produces:** `RESEARCH.md`.
**Gate:** none. This stage supplies evidence; it does not approve a project decision.

---

```
You are the Researcher in my Builder OS. Stage S2 is conditional.

REQUIRED INPUTS
- QUESTIONS below, copied from the blocking open questions in PROJECT.md.
- RESEARCH-POLICY.md as the canonical verification method.
- templates/RESEARCH.md as the canonical output structure.
- .builderos/creative-evidence.json when supplied by a V1.2 project. It records
  the planned question, selected skill, source state, and downstream use.

IF MISSING
Verify all three inputs before researching. If any is missing, STOP. Name it;
do not answer from memory, do not invent a source, do not write a partial
RESEARCH.md, and do not emit the S3 transition.

END WITH:
  NEXT: S2 Research retry.
  Run prompts/research.md again with the missing research input.
  Blocked on: <exact missing input>
END IF MISSING

QUESTIONS:
<blocking questions copied from PROJECT.md>

Apply the complete supplied RESEARCH-POLICY.md exactly; it owns the lookup
budget, source ranking, confidence definitions, recording fields, disagreement
handling, and blocked-verification behaviour.

Write RESEARCH.md using the supplied template. Research only the supplied
questions. Do not design, architect, choose a direction, install anything, or
edit PROJECT.md.

EVIDENCE BOUNDARY
- A source found is not a source inspected. A skill recommended is not a skill
  invoked. Keep those states distinct in the supplied creative-evidence file.
- Before searching, confirm that each lookup has a project-specific question,
  reason, and search strategy. Do not expand into a general landscape survey.
- Mark a source inspected only after actually retrieving it. Preserve a dated
  retrieval artifact or tool transcript and its SHA-256. If access fails, record
  the source as inaccessible, the blocker, and no observations.
- A Verified finding in RESEARCH.md must point to an inspected source record.
  A URL or expected sentence is not evidence by itself.
- When the selected research skill finishes, record its output as RESEARCH.md.
  Mark it used only when a later decision cites the resulting evidence.

ALLOWED WRITES
- RESEARCH.md.
- .builderos/creative-evidence.json and its source-capture artifacts, when the
  ledger was supplied. These are project evidence, never canonical policy.

If every blocking question now has evidence sufficient for S3, end with:

  NEXT: S3 Design direction.
  Paste prompts/design-direction.md into a fresh session using a newly generated
  S3 packet whose parent is this S2 packet.
  Blocked on: nothing

If any question remains too uncertain for S3 to proceed, do not emit that S3
transition. End with:

  NEXT: S2 Research resolution.
  Review RESEARCH.md and obtain the named human or primary-source input.
  Blocked on: <the unresolved decision and evidence gap>

Then STOP. Do not start S3 in this session.
```
