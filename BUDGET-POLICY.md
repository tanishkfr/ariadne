# BUDGET POLICY

Target: **₹2,000-3,000/month.** Up to ₹3,500-4,000 only with a strong, written justification.

Two hard constraints:

1. **Subscriptions only.** No API keys, no pay-per-token, no metered billing by default. Predictable monthly cost is worth more than marginal capability.
2. **No surprise spend.** Anything with a recurring or metered cost is Amber under [AUTONOMY-POLICY.md](AUTONOMY-POLICY.md) and requires approval before use, not after.

---

## 1. Why subscriptions only

Per-token billing turns every decision into a cost calculation, which is exactly the friction that stops people from thinking properly. A fixed monthly ceiling means the only budgeting question is *which month's limits am I spending*, which this system answers in [MODEL-ROUTING.md](MODEL-ROUTING.md) section 8.

The tradeoff, stated honestly: subscription plans have usage limits that pay-per-token does not. When you hit a limit you wait or switch tools. That is a deliberate choice — it caps downside at a known number.

**When per-token is worth breaking the rule:** a one-off batch job with a bounded, calculable cost that no subscription tool covers (a bulk image generation run, a one-time migration). Requires G2, a cost estimate in INR before starting, and a hard spend cap.

---

## 2. The budget shape

| Line | Purpose | Priority |
|---|---|---|
| Reasoning / orchestration (`R1`) | Strategy, design direction, evaluation | **Essential** |
| Implementation (`R2`) | Daily coding | **Essential** |
| Version control | GitHub | Free tier is sufficient |
| Hosting | Vercel | Free tier is sufficient for personal work |
| Fonts / assets | Per-project | Variable, charge to the client |
| Generative visual (`R5`) | Occasional | Nice to have |

Two paid lines. Everything else is free tier or per-project. If a third recurring subscription is proposed, it must displace one of the two — not be added alongside.

---

## 3. Cost snapshot

**All rows dated. Re-verify anything older than 30 days before relying on it.** Confidence levels defined in [RESEARCH-POLICY.md](RESEARCH-POLICY.md) section 3.

| Item | Price | Date checked | Confidence | Source |
|---|---|---|---|---|
| Cursor — Hobby | Free | 2026-08-21 | Verified | [cursor.com/pricing](https://cursor.com/pricing) |
| Cursor — Individual (entry) | $20/mo | 2026-08-21 | Verified | [cursor.com/pricing](https://cursor.com/pricing) |
| Cursor — Pro+ / Ultra | $60 / $200 per mo | 2026-08-21 | Reported | Third-party summaries, not seen on the official page during this check |
| **Cursor — India plan** | **₹650/mo** | 2026-08-21 | **Unverified — user-reported** | You. Not visible on the international pricing page. **Confirm at checkout.** |
| ChatGPT Plus — India | ₹1,999/mo (GST incl.) | 2026-08-21 | Reported | Multiple third-party sources; [openai.com/chatgpt/pricing](https://openai.com/chatgpt/pricing/) returned HTTP 403 during this check |
| ChatGPT Go — India | ₹399/mo | 2026-08-21 | Reported | Third-party; India-specific tier |
| GitHub Free | ₹0 | 2026-08-21 | Verified | Long-standing free tier, unlimited private repos |
| Vercel Hobby | ₹0 | 2026-08-21 | Verified | Free for non-commercial. **Client work needs a paid plan.** |

**Known gaps in this snapshot:** the official OpenAI pricing page could not be read (403), so no ChatGPT price here is Verified. The ₹650 Cursor India plan could not be confirmed from outside India. Both need a checkout-page confirmation by you — that takes two minutes and converts four Reported/Unverified rows into Verified ones.

**No exchange rate is assumed anywhere in this file.** USD prices are left in USD deliberately. Converting them here would create a fake number that goes stale in a week; convert at the day's rate plus applicable GST when it matters.

---

## 4. Recommended configuration

Based on the snapshot above, and on your stated split of Codex for reasoning and Cursor for implementation:

**Baseline — ₹1,999 + ₹650 ≈ ₹2,649/mo**

| Line | Choice |
|---|---|
| `R1` reasoning | ChatGPT Plus (₹1,999) |
| `R2` implementation | Cursor India plan (₹650) |
| Everything else | Free tiers |

This lands **inside your ideal band** with roughly ₹350 of headroom. That headroom is the reason the ₹650 plan matters: on the international $20 Cursor tier the same pair would sit near or above ₹4,000 once GST is applied, which is your justification-required territory.

**If the ₹650 plan turns out not to exist or not to fit** — the fallback order is: (a) Cursor Hobby free tier plus heavier use of `R1` for implementation, accepting slower work; (b) drop to ChatGPT Go (₹399) and put the savings into Cursor's paid tier, accepting weaker reasoning; (c) accept ~₹4,000 for one month and reassess at the 30-day benchmark ([modes/benchmark.md](modes/benchmark.md)).

Option (a) is the honest default if the ₹650 plan is unavailable. Option (b) trades away the thing this system depends on most — reasoning quality at S1 and S3 — so treat it as a last resort.

---

## 5. Before proposing anything that costs money

```
COST REQUEST (G2)
Item:        <name and plan>
Cost:        <INR/month, or INR one-time; state if converted and at what rate>
Verified:    <date + URL, or "unverified — reason">
Replaces:    <what this displaces, or "nothing — this is additive">
Without it:  <what actually cannot be done>
Trial:       <free tier or trial available? how long?>
Cancel:      <how, and is it prorated>
Recommend:   subscribe | trial first | skip
```

Rules:

- **Present the free path first**, always, even when the paid one is better.
- **"Additive" needs a stronger case than "replaces".** Two subscriptions is the plan; three is a change of plan.
- **Trial before subscribing** whenever a trial exists.
- **Never enable a paid feature to test it.** Ask first.

---

## 6. Per-project costs

Some costs belong to a project, not the monthly budget.

| Cost | Rule |
|---|---|
| Commercial font licence | Client work: quote it to the client, do not absorb it. Personal work: G2. See [LIBRARY-POLICY.md](LIBRARY-POLICY.md) section 9. |
| Stock imagery | Prefer generating or shooting. Last resort. |
| Domain | Client pays, and the client owns the registration. |
| Vercel Pro | Required for commercial use. Charge to the client. |
| CMS | Only when a non-developer edits copy. Free tiers usually suffice. |

**Client work is billed, not absorbed.** A ₹4,000 font licence on a paid project is a line item. The same licence on a personal experiment is a real budget decision.

---

## 7. Conserving what you have already paid for

The binding constraint is monthly usage limits, not rupees. The full technique list is [MODEL-ROUTING.md](MODEL-ROUTING.md) section 8. The three that matter most:

1. **Never paste a codebase into the reasoning tool.** Context burns limits faster than anything else.
2. **Documents are the compression layer.** `HANDOFF.md` exists so the implementer never re-derives what the strategist already decided. Re-deriving context is the largest recurring waste in this system.
3. **Run free local checks first.** Every build, typecheck, or Playwright run that catches a bug is a round trip you did not spend.

---

## 8. Review cadence

**Monthly:** what did each subscription actually get used for? A tool used for one thing that another tool also does is a cancellation candidate.

**At 30 days:** run [modes/benchmark.md](modes/benchmark.md) and decide with evidence rather than impression.

**Whenever a limit is hit:** record which stage was running. Repeatedly exhausting `R1` means S3 is under-specified and work is leaking into the expensive tier, not that you need a bigger plan. Buying more capacity to cover a process problem is the expensive mistake this policy exists to prevent.
