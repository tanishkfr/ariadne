# SKILL: social-strategy

**Trigger** — the user explicitly asks for social strategy, launch content, or a social content plan for the project.
**Owner** — Content strategist
**Inputs** — current project thesis, audience, strongest visual/story, available assets, supplied voice examples, and inspected current platform sources where behaviour matters
**Output** — [`SOCIAL-STRATEGY.md`](../templates/SOCIAL-STRATEGY.md) plus a hashed `social-strategy` event in `.builderos/creative-operations.json`

This is an optional planning capability. It does not publish, authenticate,
connect accounts, alter the core build stages, or become universal policy from
one post's performance.

## Method

1. Confirm explicit activation. Read the actual project documents and rendered
   evidence; do not derive a generic launch template from the mode name.
2. Identify the audience and choose one to three platforms with a
   project-specific reason. Recommending every platform fails this skill.
3. Browse current authoritative platform guidance when format, feature,
   licence, or platform behaviour affects the recommendation. Preserve the
   retrieval/capture and record it as an inspected reference before citing it.
   If current access fails, mark the claim unverified instead of filling the gap.
4. Label every important recommendation `documented`, `observed`, `inferred`,
   or `speculative`. Documented and observed claims need inspected source IDs and
   a checked date. Never promise reach or impressions.
5. Produce at least three project-specific concepts. For each, name platform,
   format, hook, and whether a CTA is genuinely useful. Define timing as a test,
   not an algorithm myth; include sequence, measurement, and one-variable-at-a-time
   iteration guidance.
6. Draft at least one post. Avoid generic announcement language, fake
   vulnerability, corporate slogans, and exaggerated claims. If no voice
   examples were supplied, mark it `rough-draft`.
7. Fill `SOCIAL-STRATEGY.md`, then record a `social-strategy` event with its
   artifact path. A revision uses a new ID and names the prior ID in `revises`;
   it never restarts the production workflow.
8. Run `builderos.py operations-check --require social`. This verifies the
   durable artifact and source hashes; it does not measure platform performance.

## Stop conditions

- No explicit social request: do not activate.
- Current platform claim cannot be inspected: record the limitation and omit or downgrade it.
- Publishing, account access, authentication, or paid distribution is requested: stop for explicit human authority.
- Insufficient voice evidence: provide a clearly marked rough draft, never an imitation claim.
