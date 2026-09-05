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
| S4, conditional | A bounded high-reasoning implementation/debugging split explicitly retained in `HANDOFF.md` | Code and return handoff for that split |
| S5 | Evaluation lenses | Rubric scores |
| S6 | Retrospective, Ariadne amendments | `RETROSPECTIVE.md`, `CHANGELOG.md` |

Roles: Strategist, Design director, Researcher, Architect, all reviewer roles, Content strategist.

## Does not own

Bulk or routine production implementation. Running commands through reasoning
instead of the terminal. Reviewing its own retained implementation. Anything
not explicitly routed to it in `HANDOFF.md`.

Codex may retain a bounded S4 split only when the handoff names the files/scope
and the work genuinely needs `R1` reasoning, such as a difficult state machine,
high-risk integration, or twice-failed diagnosis. It then consumes the same S4B
contract, runs free checks locally, and returns the same structured handoff. It
does not reinterpret the direction or grant G3.

**The rule that saves the most usage: never paste a codebase into Codex.** Paste the interface, the error, and the constraint. Context is what exhausts limits ([MODEL-ROUTING.md](../MODEL-ROUTING.md) section 8).

---

## Setup

Install the managed personal entry skill once:

```bash
python scripts/install-ariadne-skill.py install
python scripts/install-ariadne-skill.py verify
```

In a new task, invoke `$ariadne` or say “Use Ariadne” with the ordinary
brief. The skill locates this checkout and loads canonical policy through the
current generated packet. Do not paste `ROUTER.md`, `DESIGN-TASTE.md`, or the
whole Ariadne into project knowledge; that bypasses context minimisation and
creates stale copies.

For an existing repository with no Ariadne run, explicitly ask the skill to
adopt it. The runtime uses `start --adopt-existing`, preserves all current files
and behaviour, and gives S1 read-only repository context. It refuses adoption
when `PROJECT.md` or `AGENTS.md` already exists rather than overwriting a prior
state or rules file.

---

## Session discipline

**Fresh only where the boundary requires it.** Ariadne can perform compatible
reasoning work in the current task; external implementation and independent
review still receive clean, minimal contexts. The user does not compose a stage
header or reconstruct attachments.

For normal operation, invoke the repository `ariadne` skill. It discovers the
current state, runs the controller, selects the valid parent, and generates the
opening context. The low-level recovery command is:

```bash
python scripts/prepare-stage.py prepare --stage <stage> --project <project> --output <new-packet-directory> [stage options]
```

The generated `packet.txt` is the only text pasted into a required fresh session.
`manifest.json` records the parent, current Ariadne commit, source hashes,
conditional-input decisions, and the expected transcript path. Ariadne
verifies it before presenting an external action. For low-level recovery, run
`python scripts/prepare-stage.py verify --packet-dir <packet-directory>`.
Verification fails on source drift, changed parent evidence, wrong stage/parent,
missing packet sections, or S5 context leakage. Packet output must live outside
the project repository; real project packets also stay outside Ariadne.

**What to attach per stage:** the pasted stage prompt is always included. These
are its additional inputs; canonical policy and template files are transported
for that session only and are never copied into the project repository.

| Stage | Attach | Do not attach |
|---|---|---|
| S1 | The request; `skills/intake.md` unless the mode is already known to be game-experiment | Other Ariadne files |
| S2 | The blocking open questions from `PROJECT.md`; `RESEARCH-POLICY.md`; `PRIVACY-POLICY.md`; `templates/RESEARCH.md`; `.ariadne/creative-evidence.json` when present | Unrelated parts of `PROJECT.md`; the whole system |
| S3 | `PROJECT.md`; `RESEARCH.md` if it exists; `.ariadne/creative-evidence.json` when present; `DESIGN-TASTE.md`; `PRIVACY-POLICY.md`; `templates/DESIGN.md`; `skills/design-direction.md`; `skills/reference-analysis.md` only when selected; `skills/component-research.md` and `references/capabilities.json` only when selected; `DESIGN-MOTION.md` when motion applies; `DESIGN-ASSETS.md` when unresolved imagery/assets apply; reference URLs or `none yet` | Any code or build history; unselected skills |
| S4A handoff | `PROJECT.md`; approved `DESIGN.md`; project-root `AGENTS.md`; `templates/HANDOFF.md` | Code or earlier chat history |
| S4B build | The project repository; `HANDOFF.md`; approved `DESIGN.md`; project-root `AGENTS.md`; project `.ariadne/creative-operations.json`; `QA-POLICY.md`; `templates/QA.md`; `templates/RETURN-HANDOFF.md`; `skills/visual-qa.md` | Earlier reasoning/build conversations; unrelated Ariadne files |
| S5 evaluation | The URL/artifact, intent, success criteria, accepted patterns or `none`, and `EVALUATION-RUBRICS.md` | `PROJECT.md`, `DESIGN.md`, `HANDOFF.md`, `AGENTS.md`, `QA.md`, the build story, the constraints |
| S6 | `PROJECT.md`; project-root `AGENTS.md`; completed `QA.md` containing the pasted independent judgement block; `templates/RETROSPECTIVE.md` | The build or old conversations |

If a required input is unavailable, use the stage prompt's **IF MISSING** path.
Do not replace the missing canonical file from memory and do not emit the next
stage's transition.

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
| Codex absorbing the whole app | Bulk implementation stays `R2`; only the explicit retained split may be coded here |
| Pasting the codebase to ask one question | Paste the interface and the error |
| One bloated task crossing implementation or review boundaries | Ariadne creates the clean handoff; do not carry old chat history across it |
| Evaluating with the design document attached | S5 gets the URL and criteria only |
| Undated pricing or version claims | Verify or mark unverified |
| Ending with "let me know how you'd like to proceed" | Every response ends in a concrete next action |
