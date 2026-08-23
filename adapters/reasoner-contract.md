# Reasoner contract

This adapter contract translates a reasoning provider into canonical Ariadne
state. It is transport, not policy. `ROUTER.md`, `WORKFLOW.md`, project
documents, gates, stage prompts and evidence rules remain canonical.

## Required behaviour

A reasoner receives the verified current stage packet, works only within that
stage's allowed writes, writes the same canonical project documents, records
real evidence through the controller, stops at human gates, and continues from
durable project state rather than conversation history.

The contract does not require providers to expose identical internal tools,
sessions, prose or creative ideas. It requires the same outputs, gates,
evidence distinctions and handoff structure.

## Selection and switching

- Codex is the default.
- Claude is explicit opt-in and requires a detected CLI entry surface.
- Selection is project-run metadata, not project meaning.
- A switch before a packet runs creates a non-overwriting same-stage child.
- A switch after completed evidence applies to the next reasoning boundary.
- S4B remains governed by the implementation-provider record in `HANDOFF.md`.
- No reasoner may self-approve a gate or silently choose a fallback during a
  material partial output.

## Evidence and failure

Provider self-report remains self-report. Stage output is recorded structurally
or with a transcript; mechanical, observed and independent evidence remain
separate. A provider switch or failure gets its own immutable parent evidence.
A documented capability is not execution evidence.
A failed external reasoner may fall back to Codex automatically only when no
material stage output exists. Otherwise Ariadne pauses for human judgement.

## Security

The adapter never reads credentials, `.env` files or provider configuration.
It may detect the executable and run its version command. Claude sessions must
use normal permissions; bypass-permissions mode is forbidden. Installation of
the optional Claude entry skill is a separate explicit action.

## Canonical handoff parity

Both reasoners produce the existing `templates/HANDOFF.md` contract. Cursor or
Grok consumes the current S4B packet and returns the existing structured return.
No Claude-specific project document or handoff schema exists.
