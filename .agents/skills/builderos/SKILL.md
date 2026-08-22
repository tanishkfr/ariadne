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
   resume the single matching run with `status --project <project>`. If more
   than one history matches, ask which history is authoritative; never guess or
   create a second run merely because conversation history is absent.
3. For a new brief, run `builderos.py start` with the ordinary-language request.
   It creates the fresh project shell when needed, allocates the run, prepares
   S1, and starts the operations log.
4. Read the generated `packet.txt` yourself and perform the current reasoning
   stage in this task when independence does not require a fresh task. The user
   must not locate prompts, policies, templates, packet IDs, or transcript paths.
5. After a stage produces its project files, record available evidence and run
   `builderos.py prepare-next`. Let the controller discover the valid parent and
   next boundary. Supply only genuine judgement inputs that cannot be derived,
   such as whether motion/assets apply or the chosen independent-review lens.

## Human boundaries

Pause only for a decision or external action the canonical workflow reserves to
the human: creative direction, a material scope tradeoff, dependency approval,
provider/account access, shipping, or publishing. Never grant a gate.

When an external implementer is appropriate, run provider preflight first. It
reads provider, model, effort, workload, split, and reason from `HANDOFF.md`;
only live availability/quota facts may need an external check. Do not generate
the external S4B packet when preflight is blocked. Present one plain action to
the user; keep hashes and stage mechanics in `OPERATIONS.md`.

## External return

Ask the external implementer to return the generated return-handoff block. When
the user pastes or attaches it, save it to a temporary file and run
`builderos.py ingest-return`. Do not turn a summary into a verbatim transcript.
The return handoff can support continuation, but it does not prove unobserved
provider behaviour or independent QA.

For independent review, give the reviewer only the generated isolated packet.
When its marked QA judgement returns, save the response temporarily and run
`builderos.py ingest-review`. The controller preserves the raw response and
updates only QA.md's judgement region. Never paraphrase a score, verdict,
finding, or evidence limitation.

## QA and recovery

After implementation returns, inspect the recorded files and run the applicable
local checks from the delivered QA policy before independent review. Fix work
retained in the orchestrator when it is within the approved handoff. For work
owned by an external implementer, diagnose the failure and generate a
same-stage retry from the partial/blocked return; do not ask the user to rebuild packet
lineage. A retry never overwrites prior evidence and never reopens G1 unless the
finding changes the approved direction.

## Communication

Say what completed, what happens next, and whether the user needs to act. Use
plain stage names such as “project brief”, “design direction”, “implementation
handoff”, and “independent review”. Put internal IDs, manifests, hashes, and
diagnostic details in the operations log unless they affect a decision.
