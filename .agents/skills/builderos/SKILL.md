---
name: builderos
description: Start, run, resume, or recover a Builder OS creative-production project from an ordinary-language brief. Use when the user invokes Builder OS, asks to build a website/app/game/content project through Builder OS, or returns to an existing Builder OS project. Do not use for unrelated repository maintenance or a one-off code edit.
---

# Builder OS

Make the workflow feel like creative direction, not stage administration.
Canonical policy remains in the Builder OS repository; this skill operates its
runtime and never restates or replaces routing, gate, design, QA, or privacy
policy.

## Locate the runtime

Resolve the Builder OS root in this order:

1. `BUILDER_OS_HOME` when set.
2. `references/installation.json` beside this skill when installed personally.
3. The repository root containing this skill when it is loaded from
   `.agents/skills/builderos` in Builder OS itself.

The root is valid only when `scripts/builderos.py`, `ROUTER.md`, and
`WORKFLOW.md` exist. If none resolves, stop with one action: install or locate
Builder OS. Do not reconstruct its policies from this skill.

## Start or resume

1. Identify the project directory from the active workspace or the user's
   explicit path. Keep runtime packets and evidence outside the project.
2. Run `python <root>/scripts/builderos.py discover --project <project>` and
   resume the single matching run with `status --project <project>`. Treat its
   goal, approved direction, health, attention items, and next action as the
   opening briefing. If more
   than one history matches, ask which history is authoritative; never guess or
   create a second run merely because conversation history is absent.
3. For a new brief, run `builderos.py start` with the ordinary-language request.
   It creates the fresh project shell when needed, allocates the run, prepares
   S1, and starts the operations log. If the user explicitly wants to bring an
   existing repository under Builder OS, inspect its top level first and pass
   `--adopt-existing`. Adoption is non-destructive: preserve current behaviour
   and every existing file. If `PROJECT.md` or `AGENTS.md` already exists, do
   not overwrite it; discover the prior run or stop for a deliberate migration.
4. Read the generated `packet.txt` yourself and perform the current reasoning
   stage in this task when independence does not require a fresh task. The user
   must not locate prompts, policies, templates, packet IDs, or transcript paths.
5. After a same-session stage produces its project files, run
   `builderos.py advance`. It records the obvious outputs and prepares routine
   continuation without making the user operate evidence or packet commands.
   Supply only semantic choices the controller cannot derive, such as whether
   motion/assets apply or the independent-review lens. Use the lower-level
   evidence and preparation commands only for diagnosis or recovery.
6. Record a rejected direction, durable risk, lesson, or non-blocking evidence
   gap with `builderos.py record-note`; do not rely on this conversation to
   remember it. Project documents remain canonical for active decisions.

## Creative intelligence

When S1 has produced `PROJECT.md`, read
`references/creative-intelligence.md`. Interpret the project across its stated
characteristics, write the temporary assessment it defines, and run
`builderos.py creative-plan` before `advance`. This is internal machinery: tell
the user only what focused work you chose and why, not the matrix or stage IDs.

Before executing a selected method, record it as invoked with the current packet
or tool transcript as evidence. After it produces a real artifact, record it as
completed. Record it as used only after a downstream decision trace exists. Use
`builderos.py record-creative` for these events and `creative-check` before G1.
Recommended, invoked, completed, and used are never synonyms.

For external research, preserve an actual retrieval, screenshot, or provider
transcript artifact before marking a source inspected. A found URL is found;
failed access is inaccessible; neither may be described as inspected or used.
Do not let expected prose prove its own execution.

When research compares a resource or dependency, record the resource decision
defined in the same reference file: capability, fit, compatibility, licence,
cost, alternatives, necessity, inspected source, and downstream anchor. Do not
convert a comparison into an install request; G2 remains human-owned.

## Human boundaries

Pause only for a decision or external action the canonical workflow reserves to
the human: creative direction, a material scope tradeoff, dependency approval,
provider/account access, shipping, or publishing. Never grant a gate.

When an external implementer is appropriate, run provider preflight first. It
reads provider, model, effort, workload, split, and reason from `HANDOFF.md`;
only live availability/quota facts may need an external check. Do not generate
the external build handoff when `builderos.py handoff-readiness` or preflight is
blocked. Present the recommendation in plain language. When ready, give the user
one clickable packet artifact to attach or paste after they open the selected
provider; never make them search for it. Keep hashes and stage mechanics in
`OPERATIONS.md`.

## External return

The S4B packet names a unique project-local return target. Ask the external
implementer to write the complete marked return block there as well as emitting
it in the response. `builderos.py advance` ingests only the target belonging to
the current packet; a retry gets a new target and cannot overwrite prior
evidence. If the provider cannot write that target, save the returned block to a
temporary file and use `builderos.py ingest-return` as recovery. Do not turn a
summary into a verbatim transcript. The return handoff can support continuation,
but it does not prove unobserved provider behaviour or independent QA.

For independent review, give the reviewer only the generated isolated packet.
When its marked QA judgement returns, save the response temporarily and run
`builderos.py ingest-review`. The controller preserves the raw response and
updates only QA.md's judgement region. Never paraphrase a score, verdict,
finding, or evidence limitation.

## QA and recovery

After G1, read `references/creative-operations.md`. The controller derives the
approved design-to-implementation trace and project-specific visual-QA plan
automatically before S4B. After implementation, use the selected visual-QA and
creative-review methods to record rendered evidence and material drift before
independent review. These internal observations never enter the isolated S5
packet and never grant G3.

The recovery-level commands are `builderos.py operations-plan`,
`builderos.py record-operations`, and `builderos.py operations-check`; normal
progression should use `builderos.py advance` wherever it can derive the action.

After implementation returns, inspect the recorded files and run the applicable
local checks from the delivered QA policy before independent review. Fix work
retained in the orchestrator when it is within the approved handoff. For work
owned by an external implementer, diagnose the failure and generate a
same-stage retry from the partial/blocked return; do not ask the user to rebuild packet
lineage. A retry never overwrites prior evidence and never reopens G1 unless the
finding changes the approved direction.

When the user explicitly requests social strategy, use
`<root>/skills/social-strategy.md` and the conditional
`<root>/templates/SOCIAL-STRATEGY.md`.
Record current source evidence and the finished artifact through the
creative-operations contract. Do not activate social planning by default, post
content, authenticate accounts, or imply that strategy changes the build gates.

## Communication

Say what completed, what happens next, and whether the user needs to act. Use
plain stage names such as “project brief”, “design direction”, “implementation
handoff”, and “independent review”. Put internal IDs, manifests, hashes, and
diagnostic details in the operations log unless they affect a decision.
