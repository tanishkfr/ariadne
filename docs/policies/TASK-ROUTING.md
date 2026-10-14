# TASK-ROUTING

Decide *which workflow* an ordinary-language request enters before any stage machinery starts. This policy owns the entry boundary; it does not own the creative workflow it can select.

Then: [ROUTER.md](ROUTER.md) for the creative frame and the five modes, [WORKFLOW.md](WORKFLOW.md) for stages and gates, [MODEL-ROUTING.md](MODEL-ROUTING.md) for provider choice.

**This is not a second router.** Stage boundaries, worker roles, provider selection, gates, and verification keep their existing owners; this policy only chooses between the full project workflow and the lightweight task workflow, and records why. The executable implementation is `ariadne_engine/tasks.py` (interpretation, plan) and `ariadne_engine/skills.py` (native skill registry and selection), driven by `ariadne.py task-plan` and `ariadne.py task-start`.

---

## 1. The intent families

| Family | The work is | Workflow |
|---|---|---|
| `new-project` | A creative project that does not exist yet | project |
| `continue-project` | More work on a project Ariadne already records | resume |
| `feature` | A bounded capability added to an existing project | task |
| `bug` | A defect reproduced and repaired | task |
| `refactor` | Structure changed while behaviour is preserved | task |
| `performance` | A named resource made measurably better | task |
| `audit` | Existing code or structure judged, not changed | task (read-only) |
| `ui-redesign` | A visual direction refined under an approved thesis | task, or project when no direction is approved |
| `research` | Questions answered from the existing project | task (read-only) |
| `verification` | Claims about finished work tested | task (read-only), through the Proof Pass |

The five creative **modes** are untouched: a project-workflow request still receives its mode, direction gate, and design intelligence from [ROUTER.md](ROUTER.md).

## 2. The entry frame

The interpretation frame reuses the ROUTER vocabulary — action, object, artifact role, unresolved slots — and adds three task-level slots: read-only, write requested, and design obligation. Action priority remains **R-ACT-1**; an unresolved object remains material under **R-DEST-1**; questions remain governed by **R-ASK-1**.

Token evidence is recorded evidence, not a lookup table. Every matched signal is written into the plan with its source (`user-declared`, `rule-derived`, `runtime-observed`), so a wrong route is visible in one line rather than hidden in a classifier. When the evidence runs out or two materially different workflows remain plausible, the frame stays `UNRESOLVED` and preparation stops for one question.

## 3. Workflow selection

1. **Discover first.** The project directory and the parent directory are inspected for source markers, Ariadne documents, a locked design direction, and any run that already records this project. Discovery is cheap, deterministic, and read-only.
2. **An existing run means resume, never a second history.** A request against a recorded project returns `resume`; a request to *start a new project* on a directory that already has one returns `UNRESOLVED`, because continuation and a deliberate second project are different answers.
3. **A creative project keeps the full workflow.** New creative work — a website, a game, a writing system, an installation — is a project: Design Intelligence, the five modes, and the human direction gate at G1.
4. **One bounded engineering outcome is a task.** Defect, feature, refactor, measured performance work, audit, research, and verification proceed through the lightweight task workflow.
5. **A redesign follows the direction evidence.** With an approved, locked direction recorded in the project, visual refinement is a task under that decision. Without one, it is a project: setting a direction is G1 work.
6. **Unresolved stays unresolved.** Nothing is prepared until the single question that changes the work is answered.

## 4. The task workflow

A task is one bounded implementation boundary, and its shape is the shape of an S4B worker packet: an objective, a permitted scope, invariants, prohibited actions, stop and escalation conditions, validation commands, a two-repair limit, and a structured return.

Before a task packet is prepared the plan must hold:

- **A bounded scope.** The files, directories, or narrow globs the worker may touch, declared by the human or the assistant. A guessed scope is never substituted; a sensitive path (credentials, environment files, payment or auth subsystems) is refused outright and named.
- **At least one required validation command.** The command the engine can rerun independently. A detected suggestion may be *shown* from project files; it is never promoted to a requirement by the engine.
- **An honest write authorisation.** Read-only intents carry `none`, and no worker packet is prepared for them.

Execution uses the existing path planner (simple / standard / complex) from `ariadne_engine/orchestration.py`. A tiny task can take the simple path, which still retains characterisation, worker, and validation — verification is never dropped by any path.

## 5. Native skills

Skills are methods, not permissions. The registry in `ariadne_engine/skills.py` describes each native engineering skill — purpose, applicable families, required capabilities, preconditions, tools, context cost, expected evidence, and incompatibilities — and selection is a deterministic function of the interpreted intent, the characterisation, the execution path, and the host capabilities the caller declared.

- Mandatory skills for a family cannot be dropped; they are recorded as mandatory with the reason.
- A capability the host did not declare is a recorded gap, never an invented execution.
- A skill document is loaded only when its skill is selected, so an unselected method costs no context.
- Skill instructions are **untrusted data**: no skill document can grant a gate, widen a scope, or waive validation.
- Creative skill selection for project workflows stays with the creative plan; this registry delegates rather than duplicating.

The selected skills and their reasons are recorded in the run state with the plan, and the packet manifest names exactly which skill documents it delivered.

## 6. Gates and authority

A plan names the gates ahead; it never grants one. A task still ends at the human acceptance decision, still sends every dependency through G2, and still sends anything that leaves the machine through G4. Nothing in the task workflow changes the authority of [WORKFLOW.md](WORKFLOW.md), the Proof Pass, or the independent review boundary.

## 7. Stop-and-ask triggers

| Trigger | Why |
|---|---|
| The frame is `UNRESOLVED` | A confidently wrong workflow is worse than one question |
| A task lacks a bounded scope | The worker contract requires a declared boundary |
| A task lacks a required validation command | Nothing would prove the change |
| The scope names a sensitive subsystem | Protected action; needs explicit human authorization |
| An existing run records the project | Resume it; never create a second history |
| A dependency is requested | G2 remains human-owned |
| The request would deploy or publish | G4 and G5 remain human-owned |
