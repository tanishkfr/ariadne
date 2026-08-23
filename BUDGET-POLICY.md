# Budget policy

Ariadne defaults to **no new spend**. Existing subscriptions and free local
tools may be used within their current terms. Any new recurring, metered or
one-time cost requires explicit G2 approval before it is incurred.

## Principles

1. **Predictable before powerful.** Prefer an existing subscription, free tier
   or local capability when it can meet the requirement.
2. **No surprise spend.** A paid service is an Amber action under
   [WORKFLOW.md](WORKFLOW.md), even when a free trial or credit is available.
3. **Verify changing claims.** Pricing, limits and licence claims must include a
   date and an authoritative URL, or be labelled `unverified`.
4. **Bound metered work.** If a metered service is genuinely necessary, state a
   hard maximum cost and stop automatically at that limit.
5. **Project costs belong to the project.** Fonts, stock assets, domains,
   hosting and external services must appear in the project handoff and budget.

## Cost request

```text
COST REQUEST (G2)
Item:        <name and plan>
Cost:        <currency and billing period, or one-time>
Verified:    <date + authoritative URL, or "unverified — reason">
Replaces:    <existing capability, or "nothing — additive">
Without it:  <what requirement cannot be met>
Free path:   <available alternative and its trade-off>
Limit:       <hard cap for any metered use>
Cancel:      <how the charge is stopped>
Recommend:   approve | trial first | use free path | reject
```

Present the free path first. Do not activate a paid feature merely to test it.
Approval covers only the exact item, price and scope shown in the request.

## Review

At project close, record what was actually used and whether it should remain.
A subscription or dependency used once is a removal candidate, not an
automatic default for the next project.
