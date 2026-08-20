# DOCUMENT CONSISTENCY CHECKLIST

Verification that the system is internally coherent and that every requirement has a home.

Last run: **2026-08-21**.

---

## 1. Automated link check

All internal markdown links resolved, from the repository root:

```bash
python -c "
import re,os
broken=[];total=0
for root,dirs,files in os.walk('.'):
    if '.git' in root: continue
    for f in files:
        if not f.endswith('.md'): continue
        p=os.path.join(root,f); txt=open(p,encoding='utf-8').read()
        for m in re.finditer(r'\]\(([^)]+)\)',txt):
            l=m.group(1)
            if l.startswith(('http','#','mailto:')): continue
            total+=1
            if not os.path.exists(os.path.normpath(os.path.join(root,l.split('#')[0]))):
                broken.append((p,l))
print('checked',total,'broken',len(broken))
[print(' BROKEN',b[0],'->',b[1]) for b in broken]
"
```

**Result on 2026-08-21:** 491 internal links checked. **7 broken, all fixed** — 4 were missing `../` prefixes in `skills/SKILL-MANIFEST.md`; 3 pointed at `validation/` files not yet written at the time of the check.

Re-run this after any edit that moves or renames a file.

---

## 2. Requirement traceability

Every requirement from the original specification, and where it lives. **This table is the audit surface** — a requirement with no file is a gap.

### Core documents

| Required | File | Status |
|---|---|---|
| ROUTER.md — 12 required clauses | [ROUTER.md](../ROUTER.md) | Complete — see 2.1 |
| MODEL-ROUTING.md — 11 clauses | [MODEL-ROUTING.md](../MODEL-ROUTING.md) | Complete — see 2.2 |
| AGENT-ROLES.md — 12 roles × 7 fields | [AGENT-ROLES.md](../AGENT-ROLES.md) | Complete — see 2.3 |
| DESIGN-TASTE.md — 12 clauses | [DESIGN-TASTE.md](../DESIGN-TASTE.md) | Complete — see 2.4 |
| LIBRARY-POLICY.md — 11 clauses | [LIBRARY-POLICY.md](../LIBRARY-POLICY.md) | Complete |
| RESEARCH-POLICY.md — 8 clauses | [RESEARCH-POLICY.md](../RESEARCH-POLICY.md) | Complete |
| QA-POLICY.md — 12 clauses | [QA-POLICY.md](../QA-POLICY.md) | Complete |
| EVALUATION-RUBRICS.md — 9 lenses × 5 fields | [EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md) | Complete — see 2.5 |
| CONTENT-SYSTEM.md — 14 clauses | [CONTENT-SYSTEM.md](../CONTENT-SYSTEM.md) | Complete |
| AUTONOMY-POLICY, PRIVACY-POLICY, BUDGET-POLICY | Present | Complete |
| WORKFLOW, CHANGELOG, GETTING-STARTED, DAILY-PLAYBOOK, MIGRATION-CHECKLIST, README | Present | Complete |

### 2.1 ROUTER.md clause check

| Clause | Section |
|---|---|
| How modes are detected | 3.1 signals, 3.2 tie-breaks, 3.3 confidence |
| Questions per mode | 4.2, plus each mode file |
| Documents created | 10 |
| Skills activated | 10 |
| Agent responsible per stage | 10 + [WORKFLOW.md](../WORKFLOW.md) |
| When to stop and ask | 6 |
| When it may assume | 5 |
| Ambiguous requests | 3.3 Low path, 3.2 tie-break 4 |
| References / screenshots / moodboards | 7.1, 7.2 |
| Current information | 7.4 |
| Missing assets | 7.3 |
| Budget constraints | 7.5 |

### 2.2 MODEL-ROUTING.md clause check

Codex / Cursor / Claude Code responsibilities → section 3. Stronger model → 4. Fast/cheap → 5. Browser agent → 6. Visual/design skill → 7. Conserving usage → 8. Never delegate to high-cost → 8. Limit recovery → 9. Provider-neutrality → 10.

### 2.3 AGENT-ROLES.md field check

All 12 roles present. Every role carries **Purpose, Inputs, Outputs, Tools, May, Must not, Approval needed for, Hands off to**. The universal handoff format is defined once at the top rather than repeated 12 times.

**Verified:** no role can approve anything — stated in the index table and enforced per role.

### 2.4 DESIGN-TASTE.md clause check

Design 1 · Typography 2 · Colour 3 · Composition 4 · Image and texture 5 · Motion 6 · Responsive 7 · Anti-generic 8 · Reference-analysis process 9 · Original direction from multiple references 10 · Avoiding copying any one source 10 · Scorecard 11.

**All 15 rejected patterns from the specification appear** in the section 8 table, each with a "do instead".

### 2.5 EVALUATION-RUBRICS.md field check

All 9 lenses present. Criteria, 1-5 scoring, severity, evidence requirements, fixes, and the final recommendation format are defined **once in "Shared mechanics"** and referenced by each lens — deliberately, to avoid nine near-identical blocks.

### Templates, modes, adapters, deliverables

| Required | Location |
|---|---|
| 11 templates with specified sections | [templates/](../templates/) — all sections present |
| 7 modes | [modes/](../modes/) |
| 3 adapters | [adapters/](../adapters/) |
| 4 reference files | [references/](../references/) |
| Beginner setup guide | [GETTING-STARTED.md](../GETTING-STARTED.md) |
| Daily playbook | [DAILY-PLAYBOOK.md](../DAILY-PLAYBOOK.md) |
| Migration guide | [MIGRATION-CHECKLIST.md](../MIGRATION-CHECKLIST.md) |
| Tool/model routing guide | [MODEL-ROUTING.md](../MODEL-ROUTING.md) |
| Project-start prompt | [prompts/project-start.md](../prompts/project-start.md) |
| Project-review prompt | [prompts/project-review.md](../prompts/project-review.md) |
| Portfolio-evaluation prompt | [prompts/portfolio-evaluation.md](../prompts/portfolio-evaluation.md) |
| Content-system prompt | [prompts/content-system.md](../prompts/content-system.md) |
| 30-day benchmark plan | [modes/benchmark.md](../modes/benchmark.md) section 2 |
| Final validation report | [final-report.md](final-report.md) |
| 4 examples | [examples/](../examples/) |

---

## 3. Structural invariants

| Invariant | Verified how | Result |
|---|---|---|
| Every skill has a trigger and an owner | Read all 15 skill headers | Pass |
| Every skill in the manifest exists as a file | Manifest index vs directory listing | Pass — 15 + manifest |
| Every mode names its documents and skills | Read all 7 mode files | Pass |
| Every gate is defined in one place and referenced elsewhere | G1-G5 defined in [WORKFLOW.md](../WORKFLOW.md), detailed in [AUTONOMY-POLICY.md](../AUTONOMY-POLICY.md) | Pass |
| Every workflow stage has an owner and an output | [WORKFLOW.md](../WORKFLOW.md) stage table | Pass |
| No document outside `adapters/` **depends on** a product | Grep for Cursor / Codex / Claude Code / ChatGPT across all 70 files | **Pass** — but see 4, the rule is narrower than it first appears |
| Every template section from the spec is present | Field-by-field read | Pass |
| Terminology is consistent | Mode / Stage / Skill / Role / Runner / Gate used identically | Pass |

---

## 4. Known intentional exceptions

### 4.1 Product names outside `adapters/` — the measured position

An initial draft of this checklist claimed a blanket "no product names outside `adapters/`". **That was false.** A grep found product names in **17 files outside `adapters/`**, so the rule has been restated to match what the system actually does.

**The real rule: no document outside `adapters/` may contain product-specific *instructions*.** Naming a product in a declared mapping table, a cost table, an illustrative example, or an onboarding step does not create a dependency.

Measured distribution:

| Category | Files | Mentions | Legitimate? |
|---|---|---|---|
| Declared mapping table | [MODEL-ROUTING.md](../MODEL-ROUTING.md) §3 | 13 | Yes — explicitly "the only table to edit when your tooling changes" |
| Cost data | [BUDGET-POLICY.md](../BUDGET-POLICY.md) §3 | 16 | Yes — a price table without product names is useless |
| Onboarding | GETTING-STARTED, MIGRATION-CHECKLIST, DAILY-PLAYBOOK, README | 23 | Yes — must name real tools to be followable |
| Illustrative examples | skills/live-research, templates/RESEARCH, modes/benchmark, prompts/project-start | 10 | Yes — "Cursor pricing" used as an example of a *claim*, not a dependency |
| Pointers to `adapters/` | ROUTER §1, SKILL-MANIFEST, templates/AGENTS | 7 | Yes — they define "Runner" and point onward |
| Verification records | CHANGELOG, validation/ | 12 | Yes — recording what was checked |

**The portability test still passes:** no file outside `adapters/` contains an instruction that only works with one product. Swapping a tool requires rewriting one adapter file plus one row of [MODEL-ROUTING.md](../MODEL-ROUTING.md) §3.

**Re-run this grep at every retrospective.** If product-specific *instructions* have leaked outside `adapters/`, move them back.

### 4.2 Other intentional exceptions

| Exception | Where | Why |
|---|---|---|
| `prompts/` not in the original spec | [prompts/](../prompts/) | Four required deliverables needed a findable home |
| `validation/final-report.md` not in the spec | [final-report.md](final-report.md) | The required final report had no specified location |
| Repo root is `Builder OS/` not `builder-os/` | — | The folder was already named that; nesting would be redundant |

---

## 5. Contradiction check

Places where two documents could disagree, and the resolution:

| Potential conflict | Resolution | Verified |
|---|---|---|
| Design vs architecture on feasibility | Mode decides: visual modes design wins, product-app architecture wins | [AGENT-ROLES.md](../AGENT-ROLES.md) role conflicts |
| Accessibility vs art direction | Accessibility wins on Blocking; others are design decisions routed to the Design director | [skills/accessibility.md](../skills/accessibility.md) |
| Conversion lens vs creative director lens | Named as a real tension; mode decides | [EVALUATION-RUBRICS.md](../EVALUATION-RUBRICS.md) lens 7 |
| Performance vs the signature moment | Measure first, then a Design director decision, then yours. Never auto-cut. | [skills/performance.md](../skills/performance.md) |
| Project docs vs Builder OS docs | Precedence chain | [ROUTER.md](../ROUTER.md) section 8 |
| A skill's house style vs `DESIGN.md` | `DESIGN.md` outranks every skill | [adapters/claude-code.md](../adapters/claude-code.md) |
| Tailwind "default" vs "only when useful" | Consistently conditional in all four places it appears | Pass |

---

## 6. Beginner-followability

Can someone who has never used this start? Traced end to end:

[README.md](../README.md) → [GETTING-STARTED.md](../GETTING-STARTED.md) → prerequisites (**pnpm gap flagged**) → budget confirmation → tool setup → [prompts/project-start.md](../prompts/project-start.md) → Routing Block → G1 → build → [prompts/project-review.md](../prompts/project-review.md).

**Pass**, with one honest caveat: the path assumes the reader will not read all 60 files first. [GETTING-STARTED.md](../GETTING-STARTED.md) says so explicitly and gives a read-when table, but the volume is a real onboarding risk and is recorded as a weakness in [final-report.md](final-report.md).

---

## 7. Re-run schedule

| When | Run |
|---|---|
| After any file rename or move | Section 1 |
| After editing ROUTER or AUTONOMY-POLICY | [router-test-cases.md](router-test-cases.md) section D |
| After each project's retrospective | Section 5 |
| Monthly | Section 6, and delete any document you did not open |
