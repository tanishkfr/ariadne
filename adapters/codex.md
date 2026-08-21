# ADAPTER: Codex / ChatGPT

**Role in the system: the orchestrator.** It decides; it does not build.

Capability classes: **`R1`** (deep reasoning), with `R4` where browsing is available. See [MODEL-ROUTING.md](../MODEL-ROUTING.md).

> Adapters are the only files allowed to name products. Everything Codex-specific lives here, so replacing it means rewriting this file and nothing else.

---

## Owns

| Stage | Work | Output |
|---|---|---|
| S0 | Routing | Routing Block |
| S1 | Discovery, grilling | `PROJECT.md` |
| S2 | Research judgement | `RESEARCH.md` |
| S3 | Design direction, architecture | `DESIGN.md`, `ARCHITECTURE.md`, `TASKS.md`, `HANDOFF.md` |
| S5 | Evaluation lenses | Rubric scores |
| S6 | Retrospective, Builder OS amendments | `RETROSPECTIVE.md`, `CHANGELOG.md` |

Roles: Strategist, Design director, Researcher, Architect, all reviewer roles, Content strategist.

## Does not own

Writing production code. Running builds. Driving a browser against localhost. Git operations. Anything a terminal command answers.

**The rule that saves the most usage: never paste a codebase into Codex.** Paste the interface, the error, and the constraint. Context is what exhausts limits ([MODEL-ROUTING.md](../MODEL-ROUTING.md) section 8).

---

## Setup

Create a project or custom instruction set containing:

```
I use a system called Builder OS. Its documents are the source of truth.

Your role: orchestrator. You handle strategy, discovery, grilling, research
judgement, design direction, architecture, evaluation, and retrospectives.
You do NOT write production code — you produce documents that another tool builds from.

Always:
- Start by detecting the project mode and emitting a Routing Block.
- Ask a maximum of 5 questions, batched, each with a proposed default.
- Log every assumption so it can be contradicted in one line.
- Never approve your own work. Gates are human-only.
- Date and source any claim about pricing, versions, limits, or licences.
  If you cannot verify it, say "unverified" — never guess.
- End every response with one concrete next action.

Never:
- Write a full implementation. Produce a HANDOFF.md instead.
- Claim a check ran that did not run.
- Recommend installing a package without the G2 format.
```

Then paste [ROUTER.md](../ROUTER.md) and [DESIGN-TASTE.md](../DESIGN-TASTE.md) into the project's files or knowledge. Those two carry most of the system's value. Add others per session as needed — do not paste all 60 files.

---

## Session discipline

**One session per stage.** A single long thread carries S1's context into S5 and pays for it on every message. Start fresh and open with:

```
Builder OS, Stage S<n>, mode <mode>.
Attached: <the documents this stage needs>
Do: <the stage's job>
```

**What to attach per stage:**

| Stage | Attach | Do not attach |
|---|---|---|
| S1 | Nothing — just the request | Anything |
| S2 | `PROJECT.md` open questions | The whole `PROJECT.md` |
| S3 | `PROJECT.md`, `RESEARCH.md` | Any code |
| S5 evaluation | The URL and success criteria **only** | `DESIGN.md`, the build story, the constraints |
| S6 | `QA.md`, `PROJECT.md` | The build |

The S5 row is the important one. **A reviewer given the design document defends the design.** Independence is the whole point of the lens ([EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md)).

---

## Producing a handoff

The main output. Codex writes [`HANDOFF.md`](../templates/HANDOFF.md); Cursor or Claude Code consumes it without ever seeing this conversation.

Test before handing off: **could a tool that has never seen this project start work from this file alone?** If it needs the chat history, the handoff is incomplete — and the re-derivation will cost more than writing it properly.

---

## Browsing

Where browsing is available, use it for [RESEARCH-POLICY.md](../RESEARCH-POLICY.md): primary sources, dated, with URLs.

Set the lookup budget before searching, then stop and report ([RESEARCH-POLICY.md](../RESEARCH-POLICY.md) section 2).

---

## Limits

When Codex is exhausted mid-project: **stop deciding**, and do already-specified build work instead. Never let the implementation tool invent direction — see the recovery rule in [MODEL-ROUTING.md](../MODEL-ROUTING.md) section 9.

If you are at S3 without an approved thesis and Codex is out, wait. Waiting is cheaper than rebuilding.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Codex writing the whole app | It produces `HANDOFF.md`, not components |
| Pasting the codebase to ask one question | Paste the interface and the error |
| One thread for the whole project | One session per stage |
| Evaluating with the design document attached | S5 gets the URL and criteria only |
| Undated pricing or version claims | Verify or mark unverified |
| Ending with "let me know how you'd like to proceed" | Every response ends in a concrete next action |
