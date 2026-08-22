# BUILDER OS V1 READINESS

**Assessment date:** 2026-08-22

**Baseline:** `995ae95fa468baa2ef712fb56dee0cda6a22c96c`

**Rollback checkpoint:** `24c6356` — deterministic stage packet transport

## V1 STATUS

**NEAR READY**

Builder OS now has a deterministic transport path for every executable project
boundary from S1 through S6, including conditional S2 and the split S4A/S4B
boundary. Generated packets identify their stage and parent, carry exact source
hashes, reserve a transcript path, and fail closed when their source or parent
evidence changes. Cursor is ready for validation but has not been run.

This is not v1.0.0 yet. The transport and contract layer is mechanically proven;
provider behaviour and the core design-quality thesis still require the existing
real-project validation protocol.

## FIXED

| Problem | Owner | Change | Validation |
|---|---|---|---|
| Operators manually found and concatenated stage inputs | `scripts/prepare-stage.py` | Generates paste-ready S1, S2, S3, S4A, S4B, S5, and S6 packets from canonical and current project sources | Full synthetic S1→S6 chain; packet self-tests |
| Continuations could be assembled without a reliable parent or transcript | `scripts/prepare-stage.py` | Every continuation names a parent manifest and hashes the parent record and transcript; missing evidence blocks preparation | Negative tests for missing/changed evidence and wrong parent |
| Old packets could be reused after a prompt, policy, template, or project input changed | `scripts/prepare-stage.py` | `manifest.json` records SHA-256 provenance and `verify` compares every current source before reuse | Negative tests for canonical and project drift |
| A continuation could overwrite a prior record | `scripts/prepare-stage.py` | Existing output directories are refused; each retry is a new, explicit child | Duplicate-continuation negative test |
| S5 isolation depended on careful manual copying | `scripts/prepare-stage.py` | Extracts only intent, criteria, and accepted patterns; delivers only the S5 prompt and canonical rubric | Positive isolated packet plus forbidden project-context negative test |
| Conditional S2 had policy and template inputs but no pasteable entry | `prompts/research.md` | Adds the executable boundary for the existing conditional stage; unresolved evidence stays in S2 | In-fence delivery/blocked-transition guards; full-chain simulation |
| S6 produced `RETROSPECTIVE.md` without receiving its canonical template | `prompts/retrospective.md` | Requires and uses `templates/RETROSPECTIVE.md`; Codex adapter and packet map deliver it | Prompt, adapter, packet parity checks and negative tests |
| Getting-started guidance required manual prompt/file assembly and contained machine-specific setup claims | Operator documentation | Documents generated packets, evidence paths, triggers, and current limitations | Repository link and duplicate-rule checks |

## CONVENIENCE IMPROVEMENTS

The operator no longer needs to:

- locate and concatenate canonical prompt, policy, template, and project files;
- reconstruct a continuation record or decide its transcript location;
- compare a packet manually with the current Builder OS source;
- remember whether S4A or S4B applies;
- copy S5 criteria and accepted patterns while manually excluding build context;
- risk overwriting an earlier continuation or transcript;
- work out which canonical retrospective structure S6 must use.

The remaining manual work is intentional: answer material questions, decide
conditional S3 motion/asset triggers, select the independent review lens, grant
gates, operate the fresh provider session, and save its transcript.

## SKILLS

No skill changed. All four existing skills have a concrete trigger, inputs,
output, method, and stop condition. The observed V1 failures were delivery and
continuity defects; changing skill methods would have put transport behaviour in
the wrong owner and risked altering already-proven design/research policy.

## VALIDATION

- Baseline `scripts/check.py`: PASS before editing.
- Current `scripts/check.py`: PASS after the implemented changes.
- `scripts/check.py --self-test`: PASS, including positive controls and negative
  mutations for prompt delivery, S2 blocking, S5 isolation, S6 template delivery,
  and S4A→S4B parent order.
- `scripts/prepare-stage.py --self-test`: PASS, 20/20 cases.
- Synthetic chain: S1 → conditional S2 → S3 → S4A → Cursor-labelled S4B →
  isolated S5 → S6; every generated packet verified.
- `scripts/validate.py --self-test`: PASS, 21/21 guards at baseline; rerun in the
  final suite.
- No provider transcript or successful artifact was fabricated by the dry run.

## CURSOR

**Cursor READY FOR VALIDATION**

Prepared:

- a Cursor-default S4B packet built from canonical Part B and its exact inputs;
- source, parent, and transcript provenance;
- explicit exclusion of reasoning history and S5 judgement context;
- a future validation checklist in `adapters/cursor.md`;
- a deterministic positive control that generates and verifies the Cursor packet.

Not claimed: Cursor sign-in, packet ingestion, repository reading, implementation,
QA behaviour, continuation behaviour, or handoff-question count. Cursor was not
opened or run during this sprint.

## STILL UNPROVEN

- Codex and Cursor behaviour when using the new generated packets in real fresh sessions.
- Codex→Cursor handoff sufficiency and the target of at most two class-B questions.
- Test B's forced restart, implementation fidelity, browser QA, and review loop.
- Test C's three-week content learning loop.
- Provider neutrality beyond structural adapter/packet parity.
- Production deployment and rollback behaviour; no deployment was attempted.
- Whether the core thesis consistently produces better, less generic work across projects.
- A3R1's independent microphone-granted and quiet/loud evidence gap remains exactly as recorded.

## HUMAN DECISIONS REMAINING

1. Run the existing Test B protocol with Cursor and judge the real handoff and output.
2. After Test B and Test C evidence, decide whether the repository earns the v1.0.0 tag.

No human policy decision is required for the implemented transport helper; it
does not approve gates or change canonical policy ownership.

## NEXT MANUAL SESSION

1. Start one real Test B project with a generated S1 packet.
2. At G1, perform the protocol's forced restart, then approve the replacement direction.
3. Generate S4A, save its transcript, generate S4B, and follow the Cursor validation handover in `adapters/cursor.md`.
4. Record every Cursor clarification question and continue through the existing Test B procedure without changing the protocol.
