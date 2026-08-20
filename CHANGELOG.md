# CHANGELOG

How this system has changed, and why.

**Every retrospective that changes a Builder OS file logs it here.** A retrospective that changes nothing was not a retrospective ([WORKFLOW.md](WORKFLOW.md) S6).

Format: what changed, which file, what caused it. **The cause matters more than the change** — it is what tells you later whether the rule is still earning its place.

---

## Unreleased

Nothing yet.

---

## 0.1.0 — 2026-08-21

Initial system. Built in one session; **validated by dry run only, not by a real project.**

### Added

**Core** — [ROUTER.md](ROUTER.md), [WORKFLOW.md](WORKFLOW.md), [MODEL-ROUTING.md](MODEL-ROUTING.md), [AGENT-ROLES.md](AGENT-ROLES.md), [DESIGN-TASTE.md](DESIGN-TASTE.md), [AUTONOMY-POLICY.md](AUTONOMY-POLICY.md), [LIBRARY-POLICY.md](LIBRARY-POLICY.md), [RESEARCH-POLICY.md](RESEARCH-POLICY.md), [QA-POLICY.md](QA-POLICY.md), [EVALUATION-RUBRICS.md](EVALUATION-RUBRICS.md), [CONTENT-SYSTEM.md](CONTENT-SYSTEM.md), [PRIVACY-POLICY.md](PRIVACY-POLICY.md), [BUDGET-POLICY.md](BUDGET-POLICY.md)

**Onboarding** — [README.md](README.md), [GETTING-STARTED.md](GETTING-STARTED.md), [DAILY-PLAYBOOK.md](DAILY-PLAYBOOK.md), [MIGRATION-CHECKLIST.md](MIGRATION-CHECKLIST.md)

**Modules** — 15 skills + manifest, 11 templates, 7 modes, 3 adapters, 4 reference files, 4 prompts, 4 examples, 4 validation files

### Structural decisions

| Decision | Reason | Tradeoff |
|---|---|---|
| Repo root is `Builder OS/`, not a nested `builder-os/` | The folder was already named that; nesting is redundant | Diverges from the original spec |
| Added `prompts/` (not in the spec) | Four copy-paste prompts are artifacts, not documents; burying them in README makes them unfindable | One more directory |
| Added `validation/final-report.md` | The spec asked for a final report and gave it no home | One more file |
| Capability classes `R1`-`R6` instead of product names | Provider-neutrality — one table to edit when tooling changes | An extra layer of indirection to learn |
| Skills are methods, not tool integrations | They must run without special tooling | Some duplicate tool-native skills |
| Scorecard is human-scored | Taste is not mechanisable | A dishonest score defeats the mechanism entirely |
| No scripts | Nothing had a clear enough benefit to justify the maintenance | Everything is manual by default |

### Verified during construction

- pnpm **not installed** on this machine (corepack is available). Flagged in [GETTING-STARTED.md](GETTING-STARTED.md) and [MIGRATION-CHECKLIST.md](MIGRATION-CHECKLIST.md).
- gh CLI authenticated as `tanishkfr`.
- 20 Claude Code skills present at `~/.claude/skills` — **existence verified, quality and behaviour not tested.** Mapped in [adapters/claude-code.md](adapters/claude-code.md) as candidates, not recommendations.
- Cursor official pricing page: Hobby free, Individual $20/mo, Teams $40/user/mo. **No plan named "Start"** on the international page.
- ChatGPT official pricing page returned **HTTP 403** — no ChatGPT price in this system is verified.
- Cursor India ₹650/mo — **user-reported, unverified.** Not visible on the international page.

### Known weaknesses at release

Full list with severity: [validation/final-report.md](validation/final-report.md). The three that matter most:

1. **Never used on a real project.** Every claim about whether this helps is untested.
2. **The scorecard depends on honest self-scoring.** There is no mechanism preventing a generous 44 every time, and a generous score defeats the entire anti-generic apparatus.
3. **Four budget rows are unverified**, including both prices the recommended configuration depends on.

---

## How to log a change

```markdown
## 0.x.y — YYYY-MM-DD

### Changed
- <what> in <file> — because <what happened on which project>
```

Rules:

- **Name the cause, not just the change.** "Added a check for X" is not useful in six months. "Added a check for X because a font licence was discovered at S5 and cost a day" is.
- **Log removals too.** A deleted rule is as informative as an added one.
- **Anonymise.** Write the lesson, not the client ([PRIVACY-POLICY.md](PRIVACY-POLICY.md) section 1).
- **If a retrospective changed nothing, write that** — with the reason. A run of "nothing changed" entries means either the system is stable or the retrospectives are not honest, and it is worth knowing which.
