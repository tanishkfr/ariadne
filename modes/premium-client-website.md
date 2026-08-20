# MODE: Premium client website

Paid or reputation-critical work for someone else. **The strictest mode.** Over-applying it is safe; under-applying it is not.

Someone else's money and reputation are involved, and you will be judged on the result long after the project ends.

---

## Detection

**Signals:** "client", "for a company", "they want", a real brand name, money, a deadline, a brief supplied by someone else.

**Tie-break:** if someone else's reputation is at stake, this mode wins ([ROUTER.md](../ROUTER.md) 3.2).

**Not this mode if:** it is your own work (personal portfolio), or the client wants a product with accounts and state (product app).

---

## Questions

Batched, with defaults. Maximum five.

1. **Who is the client and what do they actually sell?** — no default; this cannot be assumed
2. **What must a visitor do or feel?** — default: understand the offer and make contact
3. **What assets exist?** — logo, photography, copy, brand guidelines. Default: assume only a logo exists
4. **Is there a hard deadline?** — default: none
5. **What brand rules cannot be broken?** — default: none beyond the logo

**Also establish early, even if not asked as a question:** who signs off, and whether that person has seen the references.

---

## Assumptions

| Area | Default |
|---|---|
| Pages | Home, work/services, about, contact — until told otherwise |
| Copy | You draft real copy; the client edits. Never lorem ipsum. |
| CMS | None, unless a non-developer must edit copy |
| Backend | None; form to a third-party service |
| Hosting | Vercel — **paid plan required for commercial use** ([BUDGET-POLICY.md](../BUDGET-POLICY.md) 6) |
| Domain | The client registers and owns it |
| Fonts | Licensing cost is a client line item, not absorbed |

---

## Documents

In order. All of them — this is the only mode where nothing is compressed.

`PROJECT.md` → `RESEARCH.md` → `DESIGN.md` → `ARCHITECTURE.md` → `ASSETS.md` → `TASKS.md` → `AGENTS.md` → `HANDOFF.md` → `QA.md` → `RETROSPECTIVE.md`

## Skills

discovery, **grilling (mandatory)**, live-research, reference-analysis, design-direction, component-research, asset-generation, frontend-build, motion-design, browser-qa, accessibility, performance, evaluation, deployment

## Stages

Full S1-S6, nothing compressed. See [WORKFLOW.md](../WORKFLOW.md).

## Gates

All five relevant. **G1 is non-negotiable** — client work built before direction lock produces expensive rework and awkward conversations.

Additionally: G2 for every font licence, and G4 for the production deploy to the client's domain.

---

## Quality bar

- Scorecard **43+** ([DESIGN-TASTE.md](../DESIGN-TASTE.md) section 11)
- Lenses: creative director, **strict client**, accessibility, performance
- Strict client lens **below 28 means do not present**
- Zero anti-generic patterns
- Zero placeholders, zero dead links, zero "coming soon"
- Works on the client's own phone

---

## Client-specific handling

**Privacy.** Client material is Amber before it goes to any third-party service ([PRIVACY-POLICY.md](../PRIVACY-POLICY.md) section 3). Private repo. Client names stay out of the Builder OS.

**Approval chain.** Establish who signs off at S1. A stakeholder who appears at S5 with opinions is the most common cause of rework in this mode, and it is preventable by asking one question early.

**Assets that "will come later".** Log as a risk in `HANDOFF.md` and **design a fallback that works without them.** Client-supplied assets arrive late or never. A direction that depends on unseen photography is a direction that will be rebuilt.

**Handover.** The client must be able to maintain or hand off what they own — domain, repo access, and how copy gets changed. Part of the strict-client lens, not an afterthought.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Building before the client approves the direction | G1, without exception |
| A stakeholder appearing at S5 | Establish the approval chain at S1 |
| Design blocked on assets that never arrive | Fallback designed at S3 |
| Absorbing a font licence cost | Quote it; it is a line item |
| Client work on a free Vercel tier | Check the terms; bill the plan to the project |
| Making it look like the competitor | Reference analysis, and the swap test |
| Delivering something the client cannot maintain | Handover is in the quality bar |
