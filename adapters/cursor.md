# ADAPTER: Cursor

**Role in the system: the builder.** It implements; it does not decide direction.

Capability classes: **`R2`** (fast implementation), **`R3`** (codebase reading), **`R4`** (browser). See [MODEL-ROUTING.md](../MODEL-ROUTING.md).

Roughly **80% of hours on a healthy project happen here.** If most of your time is in the reasoning tool instead, S3 is under-specified.

---

## Owns

| Stage | Work |
|---|---|
| S4 | All implementation, from `HANDOFF.md` |
| S5 | Mechanical QA, browser checks, fixing findings |
| S6 | Git operations, deploy commands |

Roles: Implementer, Motion specialist, QA engineer, and the mechanical half of the accessibility and performance reviewers.

## Does not own

The design thesis. Architecture decisions. Whether a package may be installed. Judgement-half QA — a tool that built the thing cannot review it ([EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md)).

---

## Setup

**1. Open the project only when Ariadne presents the implementation
handoff.** S1 has already created root `AGENTS.md`; Cursor reads it
automatically. Do not manually copy the canonical template into the project.

**2. The generated packet and project `AGENTS.md` already carry the relevant
rules.** The following is the expected behaviour, not a second rules file to
maintain:

```
This project follows Ariadne. AGENTS.md at the repo root is authoritative.

Before implementing:
- Read HANDOFF.md, DESIGN.md, and TASKS.md. Do not re-derive decisions from chat.
- Every value comes from the token system. Hardcoded colours, sizes, or spacing
  are a QA finding.

Never without asking:
- Install any dependency (G2)
- Push or deploy (G4)
- Add auth, a database, a CMS, or analytics
- Delete files you did not create
- Read or write .env

If the design cannot be built as specified, raise a BUILD FINDING with two
options and wait for a decision. Never substitute something easier silently.

Done means: production build passes, zero type errors, zero console errors.
Not "it renders on the dev server".
```

**3. Use pnpm.** If a Cursor agent reaches for npm, correct it — mixing package managers produces lockfile conflicts that are tedious to unwind.

---

## Working method

### Fresh-session input matrix

The stage prompt is always supplied. Ariadne policy/template files below are
session inputs, not project files; do not copy them permanently into the project.

| Stage | Supply to the fresh build session | Keep out |
|---|---|---|
| S4B build | The project repository; `HANDOFF.md`; `DESIGN.md`; project-root `AGENTS.md`; project `.ariadne/creative-operations.json`; Ariadne `QA-POLICY.md`; Ariadne `templates/QA.md`; Ariadne `templates/RETURN-HANDOFF.md`; Ariadne `skills/visual-qa.md` | Earlier reasoning/build conversations; unrelated Ariadne files |
| S5 mechanical QA | The same project repository and canonical QA inputs used at S4B | `EVALUATION-RUBRICS.md`; independent judgement belongs to the fresh Reviewer session |
| S6 ship action | The branch/target, completed `QA.md`, explicit human G3 approval, and the one approved G4 ship request | Design chat and reviewer conversation |

If a required S4B input is unavailable, follow Part B's **IF MISSING** block and
stop in S4. Do not substitute a remembered policy or advance to S5.

In normal use, Ariadne prepares Cursor's S4B input after provider preflight;
the operator does not assemble it. The low-level recovery command remains:

```bash
python scripts/prepare-stage.py prepare --stage S4B --project <project> --output <new-packet-directory> --parent <S4A-packet-directory>
```

The S4B default provider in the manifest is `cursor`. The packet contains the
current canonical Part B, `HANDOFF.md`, locked `DESIGN.md`, project `AGENTS.md`,
`.ariadne/creative-operations.json`, `QA-POLICY.md`, `templates/QA.md`,
`templates/RETURN-HANDOFF.md`, and `skills/visual-qa.md`; it contains no
reasoning transcript. The packet names one project-local structured return
target. Writing the marked return block there lets `ariadne.py advance` ingest
it without manual copying; each retry has a different non-overwriting target.
Open Cursor at the project repository, start a fresh chat, paste `packet.txt`,
and return the completed `templates/RETURN-HANDOFF.md` block at the packet's
return target. Ariadne ingests that block and manages its evidence path. A verbatim transcript is preserved
when available but is never reconstructed from the return summary.

**Start each task fresh.** New chat per `TASKS.md` item. Open with:

```
Task <n> from TASKS.md.
Read HANDOFF.md and DESIGN.md first.
Acceptance criterion: <paste it>
Branch: s4/<slug>
```

**One task, one branch.** Never on `main`. This is what makes almost all agent work reversible with `git checkout`, and it is why the Green tier in [WORKFLOW.md](../WORKFLOW.md) can be as permissive as it is.

**Let it read the codebase; do not paste the codebase.** Cursor's indexing is `R3` — that is what it is for. Pasting files into a reasoning tool is the expensive alternative.

**Verify in increments.** Build after each meaningful change. Catching a break within one change is minutes; ten changes later is an afternoon.

**Production build, not dev server.** `pnpm build` is the standard for "done". The dev server hides hydration errors, build failures, and font loading problems — exactly the class of bug that surfaces first on the deployed preview.

---

## Browser QA in Cursor

Use the browser tooling for `R4` work: loading routes, reading the console, checking responsive widths, capturing screenshots.

Browser-agent passes are where usage disappears; scripts are free. Turn repeat checks into Playwright tests ([QA-POLICY.md](../QA-POLICY.md)).

Escalation ladder, cheapest first: production build → typecheck → Playwright → browser agent → your own eyes. Do not skip rungs upward ([QA-POLICY.md](../QA-POLICY.md)).

---

## Cloud agents, MCP, hooks, plugins

Cursor offers these. Treat them as **optimisations, never requirements** — that is what keeps the system portable ([MODEL-ROUTING.md](../MODEL-ROUTING.md) section 10).

| Feature | Sensible use | Caution |
|---|---|---|
| Cloud agents | Long refactors, parallel independent tasks | Still one task per branch; still G2 and G4 |
| MCP servers | Reaching a real data source during a build | Each one is a dependency and a privacy surface ([PRIVACY-POLICY.md](../PRIVACY-POLICY.md)) |
| Hooks | Auto-running build or lint after edits | Genuinely useful; catches things early for free |
| Plugins / skills | Repeated project setup | Do not encode design judgement into a plugin |

**Never encode the design thesis into tooling.** The thesis is per-project and belongs in `DESIGN.md`. A reusable "make it look good" rule produces the same output every time, which is the definition of generic.

---

## Limits

When Cursor is exhausted: move to `R6` work — tests, build fixes, cleanup, documentation — or hand the same `HANDOFF.md` to Claude Code. **The handoff is plain markdown precisely so this switch costs nothing.**

Do not switch to the reasoning tool to write code. That is the most expensive way to do the cheapest work.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Silently building something easier than specified | BUILD FINDING with two options |
| Installing a package to "just try it" | G2 first; scratch branch if prototyping |
| Working on `main` | One task, one branch |
| Hardcoded values drifting from the design | Token system first; sweep for literals |
| "Works on my dev server" | Production build is the standard |
| Re-explaining decisions every session | It is in `HANDOFF.md`; if not, that is the bug |
| Cursor reviewing its own output | Judgement QA runs elsewhere |
| npm creeping in | Correct it immediately |
