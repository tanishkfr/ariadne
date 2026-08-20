# EXAMPLE: Premium client website

> **Fictional worked example.** No real client. It shows how the strictest mode handles missing assets, licensing, and an approval chain — the three things that actually go wrong on client work.

**Request:** *"Build a clean, high-end website for a serious client."*

---

## S0 — Routing

Note the confidence level. The request is vague about *who*, but the mode is not in doubt.

```
ROUTING BLOCK
Mode:         premium-client-website  (confidence: High)
Runner-up:    personal-portfolio — rejected: "for a client" means someone
              else's reputation, which wins the tie-break
Stage:        S0 -> S1
Questions:    5 (batched)
Assumptions:  Home / work / about / contact until told otherwise. Real copy
              drafted by us. No CMS. No backend — form to a third-party service.
              Vercel PAID plan (commercial use). Client owns the domain.
Documents:    PROJECT, RESEARCH, DESIGN, ARCHITECTURE, ASSETS, TASKS, AGENTS,
              HANDOFF, QA, RETROSPECTIVE  (all of them — nothing compressed)
Skills:       all 14 for this mode
Owner:        Strategist on R1
Gates ahead:  G1, G2 (every font licence), G3, G4
Budget:       Vercel paid plan + any font licence — both billed to the client,
              not absorbed
First action: Answer the 5 questions. Question 5 is the one that will bite later.
```

**Questions:** who is the client and what do they sell · what must a visitor do or feel · what assets exist · hard deadline · what brand rules cannot be broken.

**Plus, established immediately even though it is not one of the five: who signs off.**

---

## The three things that actually go wrong

### 1. "Clean, high-end" is not a brief

It is the same failure as "clean, modern, minimal" in a design thesis — it describes a category, not a direction, and every competitor's site would satisfy it.

Grilling turned it into: *the client sells a slow, expensive, handmade product, and their competitors all look fast and cheap.* That is a direction — **the site should feel slow on purpose.** Long transitions, generous space, nothing hurried.

Thesis: *A site that takes its time, because the product does.*

### 2. Assets that "will come later"

The client promised photography "in two weeks". It did not arrive. This is the single most common client-work failure and it is entirely predictable.

The rule ([ROUTER.md](../../ROUTER.md) 7.3): **no project reaches S4 with an unresolved asset on the critical path.**

Resolution at S3, before it became a problem: the direction was made **type-led**, with photography as an enhancement rather than a dependency. `ASSETS.md` recorded a fallback for every image slot. When the photography arrived late, it slotted in. Had it never arrived, the site still worked.

**A direction that depends on unseen photography is a direction that will be rebuilt.**

### 3. Font licensing

The chosen display face was free for personal use. On a commercial client site that is a real liability, not a technicality.

Caught at **S3 via G2**, not at launch. Options presented to the client: buy the licence (₹X, a line item on the invoice) or substitute a comparable open face. Client chose to buy.

**Cost of catching it at S3:** one email. **Cost of catching it after launch:** a rebuild of the type system plus an awkward conversation about liability.

---

## Approval chain

Established at S1: *who signs off?*

The answer was "me and my business partner" — and the partner had never seen the references. A stakeholder appearing at S5 with opinions is the most common cause of client rework, and it is preventable by asking one question at S1 and then showing both people the direction at G1.

---

## S5 — Lenses

Creative director · **strict client** · accessibility · performance.

The strict-client lens is deliberately unsympathetic and asks the question that matters: *would I pay the second invoice?* Below 28 means do not present.

It also checks the thing designers forget: **handover readiness.** Can the client maintain what they own — domain, repo access, how copy gets changed? That is part of the quality bar, not an afterthought.

---

## What this example demonstrates

| Point | Where |
|---|---|
| The tie-break biases toward the stricter mode | Runner-up rejected in the Routing Block |
| "Clean and high-end" is a category, not a direction | Grilling produced "slow on purpose" |
| Asset dependencies are resolved at S3 | Type-led direction; fallback per slot |
| Licensing is caught by G2, not at launch | One email versus a rebuild |
| The approval chain is an S1 question | Prevents the S5 stakeholder |
| Client costs are billed, not absorbed | Vercel plan + font licence |
