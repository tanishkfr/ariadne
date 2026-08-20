# FINAL VALIDATION REPORT

Builder OS v0.1.0 · built 2026-08-21 · `C:\Vibe Coding\Real Stuff\Builder OS`

---

## 1. What was created

**71 markdown files** (this report included). Nothing else — no code, no dependencies, no scripts. The workspace was empty before this; no existing work was touched.

| Group | Count | Location |
|---|---|---|
| Core documents | 18 | repository root |
| Skills + manifest | 16 | [skills/](../skills/) |
| Templates | 11 | [templates/](../templates/) |
| Modes | 7 | [modes/](../modes/) |
| Adapters | 3 | [adapters/](../adapters/) |
| References | 4 | [references/](../references/) |
| Prompts | 4 | [prompts/](../prompts/) |
| Examples | 4 | [examples/](../examples/) |
| Validation | 3 + this | [validation/](../validation/) |

**Verified, not asserted:** 559 internal links checked programmatically, all resolving. Seven were broken during construction and fixed. The provider-neutrality claim was **measured and found overstated**, then corrected — see [document-consistency-checklist.md](document-consistency-checklist.md) §4.1.

## 2. Where the important files are

| Need | File |
|---|---|
| Start a project | [prompts/project-start.md](../prompts/project-start.md) |
| How routing works | [ROUTER.md](../ROUTER.md) |
| **The quality bar** | [DESIGN-TASTE.md](../DESIGN-TASTE.md) — the highest-value file here |
| Which tool does what | [MODEL-ROUTING.md](../MODEL-ROUTING.md) |
| What needs approval | [AUTONOMY-POLICY.md](../AUTONOMY-POLICY.md) |
| Whether to install a package | [LIBRARY-POLICY.md](../LIBRARY-POLICY.md) |
| How to verify a build | [QA-POLICY.md](../QA-POLICY.md) |
| How to judge finished work | [EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md) |
| Daily use | [DAILY-PLAYBOOK.md](../DAILY-PLAYBOOK.md) |
| First-time setup | [GETTING-STARTED.md](../GETTING-STARTED.md) |

## 3. How to initialise a new project

1. Copy [prompts/project-start.md](../prompts/project-start.md) into your reasoning tool, replacing the last line with your request.
2. Answer up to 5 questions.
3. Follow the Routing Block's **First action**.
4. At **G1**, read the design thesis. **If it contains "clean", "modern", "minimal", or "premium", reject it.** That is a mood, not a direction.
5. After G1, copy [templates/AGENTS.md](../templates/AGENTS.md) to the project root and hand `HANDOFF.md` to your build tool.

## 4. Which tool to open first

**The reasoning tool (Codex), if nothing exists yet.** Otherwise the build tool.

| Give Codex | Give Cursor | Give Claude Code |
|---|---|---|
| [ROUTER.md](../ROUTER.md) + [DESIGN-TASTE.md](../DESIGN-TASTE.md) in project knowledge | `AGENTS.md` at the repo root | Same `AGENTS.md` |
| The instruction block from [adapters/codex.md](../adapters/codex.md) | The rules block from [adapters/cursor.md](../adapters/cursor.md) | [adapters/claude-code.md](../adapters/claude-code.md) |
| Per session: only that stage's documents | `HANDOFF.md` + one task | Same `HANDOFF.md` |
| **Never** the codebase | The repo (let it index) | The repo |

**Do not upload all 70 files anywhere.** You pay for that context on every message.

## 5. Skills per project type

Full table: [skills/SKILL-MANIFEST.md](../skills/SKILL-MANIFEST.md) "Activation by mode". Summary — client site gets all 14; portfolio drops live-research and component-research; product app drops reference-analysis and motion; game gets 6; content gets 5; audit gets 5.

## 6. Documents to create first

| Mode | First three |
|---|---|
| Client site | PROJECT → RESEARCH → DESIGN |
| Portfolio | PROJECT → DESIGN → ARCHITECTURE |
| **Product app** | PROJECT → **ARCHITECTURE** → DESIGN *(the only mode where architecture precedes design)* |
| Game | PROJECT (short) → DESIGN (short) → TASKS |
| Content | PROJECT → RESEARCH → CONTENT-LEARNINGS |
| Audit | QA only |

## 7. How to conserve usage

The three that matter ([MODEL-ROUTING.md](../MODEL-ROUTING.md) §8): **never paste a codebase into the reasoning tool** · **let `HANDOFF.md` carry decisions** so nothing is re-derived · **run free local checks first**.

Never send to a high-cost model: build output, test output, lint errors, file listings, git operations, or "is this working?" when a command answers it.

## 8. Library selection

Default answer is **build it yourself**. Component libraries are research, not dependencies ([references/ui-libraries.md](../references/ui-libraries.md)).

**The dividing line: install for correctness, build for expression.** A focus trap is correctness — use Radix. A hover interaction in your signature moment is expression — build it, or it looks like everyone else's.

Every package goes through the G2 format in [LIBRARY-POLICY.md](../LIBRARY-POLICY.md) §6. Styled kits (MUI, Chakra, Ant) are forbidden by default because they make art direction impossible.

## 9. How to run visual QA

Cheapest first, never skipping upward: **production build → typecheck → Playwright → browser agent → your own eyes.** Anything checked twice becomes a Playwright test.

Then the judgement half: the scorecard, the 15-row anti-generic sweep, and 2-4 review lenses in **fresh sessions**. A build that passes every mechanical check and scores 2/5 on creative direction has failed. Both halves are pass/fail.

## 10. How to evaluate "feel"

Three proxies ([skills/evaluation.md](../skills/evaluation.md)):

- **Five-second test** — can they describe something specific, or only the category?
- **Swap test** — replace logo and copy with a competitor's. Still works? It is a template.
- **Recall test** — describe it tomorrow without looking. What survives?

All three failing means the work is competent and forgettable. That is an **S3 problem surfacing at S5**, and polish will not fix it.

## 11. How to update the Builder OS

Every retrospective answers "what changes in the Builder OS?" **by editing the file**, then logging it in [CHANGELOG.md](../CHANGELOG.md) with the cause. Log the cause, not just the change — it is what tells you later whether the rule still earns its place.

Write the lesson, not the case. "Verify font licences at S3" belongs here. "Client X's typeface" does not.

---

## 12. What remains manual

Honestly, and deliberately:

| Manual | Why |
|---|---|
| **Every gate** (G1-G5) | The point. Approval is not delegable. |
| **Scoring the scorecard** | Taste is not mechanisable |
| Posting content | Structural. No account access, by design. |
| Setting environment variables | Security |
| Confirming prices at checkout | Only checkout is Verified |
| Looking at screenshots | Capturing evidence and checking it are different acts |
| Deciding a mode change | It is a scope change, so it is yours |

## 13. What is not automated (and could be)

| Not automated | Could be | Why it was not |
|---|---|---|
| Creating a project scaffold from templates | A script | No verified need yet. Building automation before the manual version has been run twice is how unused tooling accumulates. |
| The link checker | A pre-commit hook | The one-liner in the checklist works; a hook needs maintaining |
| Anti-generic sweep | Partly lintable (hardcoded literals, missing focus styles) | The interesting half — "is this generic?" — is not detectable by a linter |
| Re-verifying stale research | A date-check script | Wait until enough `RESEARCH.md` files exist to make it worthwhile |

**No scripts were written.** Every candidate failed the test in your brief: *does this have a clear user benefit today?* Revisit after the 30-day benchmark, when there is evidence of what is actually repetitive.

---

## 14. Remaining weaknesses, ranked

Ordered by how likely they are to hurt you.

**1. Never used on a real project.** Every claim about whether this helps is untested. Dry runs verify the router is internally consistent; they prove nothing about output quality. → [modes/benchmark.md](../modes/benchmark.md) §2 exists for exactly this.

**2. The scorecard depends on honest self-scoring.** Nothing prevents a generous 44 every time, and a generous score defeats the entire anti-generic apparatus. This is the single largest structural weakness and it has **no mechanical fix** — only the discipline of naming the lowest criterion and its evidence.

**3. Four budget rows are unverified,** including both prices the recommended ₹2,649 configuration depends on. The ChatGPT page returned 403; the ₹650 Cursor plan is user-reported and invisible from outside India. **Two minutes at checkout fixes this.**

**4. The Low-confidence router path was never exercised.** All five dry runs returned High confidence because all five were clear. Ambiguous requests and the mode-switch procedure are the paths most likely to be wrong. → [router-test-cases.md](router-test-cases.md) sections A and E.

**5. Volume is an onboarding risk.** 70 files is a lot, and reading them all before building is the most likely first-week failure. [GETTING-STARTED.md](../GETTING-STARTED.md) mitigates with a read-when table, but the risk is real.

**6. Installed Claude Code skills are unverified.** Their existence is confirmed; their quality and behaviour are not — I did not run any of them. Several carry strong aesthetic opinions that can override your `DESIGN.md`. → [adapters/claude-code.md](../adapters/claude-code.md) cautions.

**7. Reference mechanism columns are empty.** [references/visual-references.md](../references/visual-references.md) is a register, not an analysis. Filling it out of context would have produced generic notes — the exact failure this system prevents. It fills in as you use references on real projects.

**8. Codex and Cursor adapters are untested.** Written from your description of your setup; neither tool was available in this environment. The instruction blocks are plausible, not verified.

**9. `prefers-reduced-motion` and accessibility rules are written, not exercised.** No build exists to test them against.

**10. Two gates may prove to be friction.** G2 on every package and G5 on every post are deliberately strict. If they get waived routinely, they are not functioning as gates — the retrospective template asks about this explicitly.

---

## 15. The first five actions

1. **`corepack enable`** — pnpm is not installed and every default assumes it.
2. **Confirm the ₹650 Cursor plan and your real ChatGPT charge at checkout.** Write both into [BUDGET-POLICY.md](../BUDGET-POLICY.md) §3 with today's date. Two minutes, and it converts the four weakest rows in this system.
3. **Set up Codex** with the block from [adapters/codex.md](../adapters/codex.md) and upload **only** [ROUTER.md](../ROUTER.md) and [DESIGN-TASTE.md](../DESIGN-TASTE.md).
4. **Run one small game-experiment end to end.** Do not read the rest of the documentation first. Stop properly at G1 and judge the thesis.
5. **Run [prompts/project-review.md](../prompts/project-review.md) on the result in a fresh session.** Then do a 15-minute retrospective and edit one Builder OS file.

---

## 16. Definition of done, checked

| Requirement | Status |
|---|---|
| Start a new project with one prompt | Yes — [prompts/project-start.md](../prompts/project-start.md) |
| Router selects the correct mode | Yes on 5 clear cases; **ambiguous cases untested** |
| Required documents generated | Yes — 11 templates, per-mode sets |
| Agents know their responsibilities | Yes — 12 roles with approval boundaries |
| Libraries require justification | Yes — G2, forbidden-by-default criteria |
| Design quality evaluated explicitly | Yes — scorecard + 9 lenses + anti-generic sweep |
| Browser and visual QA in the workflow | Yes — S5, escalation ladder |
| GitHub and Vercel fit naturally | Yes — one task per branch, preview per branch, G4 |
| Works without APIs by default | Yes — subscriptions only, paid APIs are Amber |
| Clear daily instructions | Yes — [DAILY-PLAYBOOK.md](../DAILY-PLAYBOOK.md) |
| Explainable in under ten minutes | Yes — [README.md](../README.md) "How it works" plus the 5 rules in [GETTING-STARTED.md](../GETTING-STARTED.md) |

**Met on construction. Not met on proof** — every row above describes what the system specifies, not what it has been shown to produce. That distinction is the honest state of this deliverable, and the 30-day benchmark is how it gets closed.
