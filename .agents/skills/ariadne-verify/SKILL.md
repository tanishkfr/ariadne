# Ariadne Verify — thin conversational integration

Teach an assistant when to invoke Ariadne, how to recover the request,
how to identify the work, and how to present results faithfully.

No acceptance logic lives here. This skill calls:

```
MCP -> Ariadne stable API -> Acceptance / Verification engine
```

## When to invoke

- `@Ariadne verify what the agent just did.`
- `@Ariadne verify this PR against the original issue.`
- `@Ariadne check whether Codex actually finished everything I asked for.`

Invoke when the conversation already contains an original request and
some produced work. Do not ask the user to retype what is already present.

## How to recover the original request

1. Use the earliest user message that states the outcome wanted.
2. Keep it verbatim where possible; do not paraphrase obligations away.
3. If multiple requests exist, ask which one is under verification.
4. Never invent requirements the user did not state.

## How to identify the work

- Work revision: file tree, PR diff, commit, or artifact set.
- Worker identity: which producer made it (codex, claude-code, cursor,
  opencode, devin, boreal, ci, human, custom-agent).
- Worker claims: completion statements as quoted by the worker.
- Evidence refs: tests, builds, screenshots, renders actually present.

Workers may submit evidence. Workers cannot submit acceptance.

## How to call

Prefer MCP in order:

```
create_verification_contract(task_text, task_id)
verify_work(task_text, work_ref/work_digest, completion_statements)
get_verification(proof_id)
compare_verifications(before, after)
```

Or CLI:

```bash
ariadne verify --against task.md --work-root ./work --json
ariadne proof VP-0001
ariadne compare VP-0001 VP-0002
```

## How to present results faithfully

- Show requirement-level verdicts: PROVEN, PARTIAL, UNPROVEN, FAILED, NEEDS_HUMAN.
- Show contradicted worker claims separately.
- Show VERDICT: ACCEPTED or NOT_ACCEPTED.
- Never render UNPROVEN as done.
- Never report a percentage quality score.
- Permitted: "Evaluated against 8 requirements using Proof Pass VP-0041."
- Never: bug-free, perfect, fully secure, certified correct, guaranteed.

## What this skill must not do

- No duplicate verification engine.
- No reviewer-identity or human-approval minting.
- No marketplace publication claims.
- No hosted-service claims unless externally verified.
