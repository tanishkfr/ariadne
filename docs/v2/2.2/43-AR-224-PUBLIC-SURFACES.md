# AR-224 Public Surfaces

## CLI

```
ariadne verify --against task.md --work-root ./work
ariadne verify
ariadne verify --json
ariadne proof VP-0001
ariadne proof VP-0001 --json
ariadne compare VP-0001 VP-0002
```

Zero-arg `ariadne verify` resolves the single active contract or fails
clearly. Ambiguity never silently picks a task. Internal compiler plumbing
is not normal UX.

CI exit codes: 0 ACCEPTED, 1 NOT_ACCEPTED, 2 VERIFICATION_BLOCKED,
3 usage/configuration error. Requirement failed never looks like a crash.

## Stable Python API (STABLE)

```
create_contract(task_text, task_id)
verify(task_text, work_ref/work_digest, completion_statements)
get_verification(proof_id)
compare_verifications(before, after)
```

Classification lives in `src/ariadne_engine/public.py`:
STABLE (major-version break only), PROVISIONAL (may evolve within v2),
INTERNAL (no product promise). The release gate asserts every exported
api name carries exactly one classification.

## MCP (schema ar-224-mcp-1)

Tools: create_verification_contract, verify_work, get_verification,
compare_verifications. Delegation is always MCP to stable API to engine.
All inputs untrusted: path traversal, proof-ID forgery, reviewer forgery,
human-approval forgery, contract replacement, evidence laundering, prompt
injection, oversized payloads and command injection fail closed.
MCP cannot mint authority.

## ChatGPT integration

Thin skill in `.agents/skills/ariadne-verify/SKILL.md` over the same
API/MCP surface. Teaches when to invoke, how to recover the request from
conversation, how to identify work/claims/evidence, and how to present
requirement-level results without turning UNPROVEN into done.
No acceptance logic in the conversational layer. No marketplace
publication claims.

## Worker handoff (agent-neutral)

Schema `ar-224-worker-handoff-1`: task identity, work revision, worker
identity, producer (codex/claude-code/cursor/opencode/devin/boreal/ci/
human/custom-agent), completion claims, evidence refs. Workers may submit
evidence; workers cannot submit acceptance. Core semantics contain no
vendor-specific completion rules.

## GitHub / CI

Example in `examples/ci-verify/ariadne-verify.yml`: issue/spec to PR/change
to tests/build/runtime evidence to `ariadne verify` to Proof Receipt
artifact. No hosted GitHub App required.

## OSS parity

Contracts, claims, evidence evaluation, verification, acceptance, Proof
Pass, receipts, comparison and MCP ship in OSS. Hosted value later is
convenience only.

## Design workflow (first-class)

User request to project/context inspection to content model to concept
exploration to reference acquisition to category-default analysis to
direction recommendation to G1D human approval to implementation to render
to fresh-eyes critique to bounded refinement to verification.
Routine work continues autonomously after approval.
