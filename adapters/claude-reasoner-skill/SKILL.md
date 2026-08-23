---
name: builderos
description: Run or resume a Builder OS creative-production project through the optional Claude reasoner adapter. Use only when the user explicitly chooses Claude or invokes Builder OS from Claude Code.
---

# Builder OS — Claude reasoner entry

This is a thin provider entry adapter. Canonical policy, project meaning, gates,
prompts and output formats remain in Builder OS. Do not restate them here and do
not create a project `CLAUDE.md`.

## Locate and verify

Read `references/installation.json` beside this skill. It names the active
Builder OS runtime. Stop if it is missing, its root is unavailable, or
`scripts/builderos.py`, `adapters/reasoners.json`, `ROUTER.md` or `WORKFLOW.md`
is missing. Do not reconstruct any of those files from this skill or memory.

For a known project, run:

```text
python <root>/scripts/builderos.py discover --project <project>
python <root>/scripts/builderos.py status --project <project>
python <root>/scripts/builderos.py reasoner-status --project <project> --reasoner claude
```

If no run exists, start the ordinary-language request with `--reasoner claude`.
For an existing run whose selected reasoner is not Claude, use
`select-reasoner --reasoner claude --reason "Explicit user choice in Claude
Code."`. Never edit provider metadata by hand.

## Execute the current boundary

Read and verify only the current generated `packet.txt`. It carries the
canonical stage prompt, policies, templates and project inputs allowed at that
boundary. Use the project files named by the packet as durable state; session
history is disposable.

Write only the canonical outputs allowed by the packet. Run `builderos.py
advance` after same-session work. Never grant a gate. Never copy packet policy
into the project. At S4B, stop and present the verified implementation packet
for the provider selected by `HANDOFF.md`; this optional skill does not turn
Claude into the V1.5.1 implementer.

For isolated S5, start fresh and use only the current S5 packet. Do not request
or inspect design, handoff, QA, source or build-history context.

When the user explicitly requests project distribution or supplies social
performance data, use the shared runtime `skills/social-strategy.md`,
`templates/SOCIAL-STRATEGY.md`, and conditional
`templates/CONTENT-LEARNINGS.md`. Read current project evidence directly and
record the same provider-neutral social strategy, result, and learning events.
Claude may draft and reason here; it cannot publish, fabricate metrics, grant
G5, or claim live social behaviour without user-supplied evidence.

## Failure

If Claude cannot continue, run `record-reasoner-failure` with a concrete
summary and honest evidence class. The controller falls back to Codex only when
no material current-stage output exists. If material output exists, stop for
human judgement. Never delete partial output, overwrite evidence, or claim a
fallback completed work it did not execute.

## Stop conditions

Stop when the runtime or packet is missing/stale, Claude capability detection
is blocked, an input required by the packet is absent, a human gate is reached,
or the current boundary belongs to the external implementer. End with the one
concrete action named by the current verified state.
