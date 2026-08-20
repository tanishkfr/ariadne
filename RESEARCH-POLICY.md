# RESEARCH POLICY

How the system tells the difference between a fact and a memory.

Core rule: **a model's training data is a snapshot of the past presented with the confidence of the present.** Anything that changes over time must be looked up, dated, and sourced — or explicitly marked unverified.

Owned by the Researcher ([AGENT-ROLES.md](AGENT-ROLES.md)). Skill: [skills/live-research.md](skills/live-research.md).

---

## 1. What requires live verification

**Always verify. Never answer from memory:**

| Category | Examples |
|---|---|
| Pricing and plans | Subscription costs, tiers, regional pricing, limits, free-tier terms |
| Model and tool capability | Which models exist, context sizes, rate limits, feature availability |
| Library status | Current major version, last release, maintenance, framework compatibility |
| Breaking changes | Migration requirements, deprecated APIs |
| Platform rules | Deployment limits, build minutes, bandwidth, social platform character limits and policies |
| Licences | Font EULAs, package licences, asset terms |
| "Best current" anything | Best library for X, current best practice, what people use now |
| Whether a thing still exists | Products get discontinued, renamed, acquired |

**Safe from memory** (stable, or verifiable by running something):

| Category | Why |
|---|---|
| Language and CSS fundamentals | Stable |
| Design principles, typography, colour theory | Not versioned |
| Algorithms, data structures | Stable |
| Anything in this repository | You wrote it |
| Anything a command answers | Run the command instead — cheaper and definitive |

**The trigger question:** *could this have changed since the model was trained, and would being wrong cost me anything?* Both yes means verify.

---

## 2. Source preference

In order. Prefer a lower number when sources disagree.

1. **Official primary** — the vendor's own pricing page, the package's repository, the framework's docs, the actual `LICENSE` file.
2. **Machine-readable registry** — npm registry data, GitHub API, `bundlephobia`.
3. **Official secondary** — vendor changelog, release notes, status page, official blog.
4. **Reputable independent** — well-known technical publications, maintainer posts, conference talks.
5. **Community** — Stack Overflow, Reddit, Discord. Useful for *whether a problem exists*, not for *what is true*.
6. **SEO content farms and "Top 10 X in 2026" blog posts** — treat as a pointer to a primary source, never as evidence. These are frequently generated, frequently wrong, and frequently stale despite a current date in the title.

**Regional pricing warning.** Pricing pages often localise by IP. A price seen from one country may not be what you are charged in India, and third-party summaries almost never get INR right. Verify at checkout, and mark anything not seen at checkout as unverified.

---

## 3. Recording

Every researched claim carries four things: **claim, date, source URL, confidence.** Anything missing one of these is not research.

| Confidence | Means | Use |
|---|---|---|
| **Verified** | Seen on an official primary source today | Safe to act on |
| **Reported** | Consistent across two or more independent secondary sources | Act on it, flag it |
| **Unverified** | Single weak source, or user-reported, or blocked | Do not build a decision on it without a check |
| **Contradicted** | Sources disagree | Record all versions, do not average |

**Freshness.** A fact older than **30 days** for pricing/limits, or **90 days** for library status, is re-verified before it is relied on again. Old research is not deleted — it is dated, and superseded rows stay for the history.

Format and worked example: [templates/RESEARCH.md](templates/RESEARCH.md).

---

## 4. Handling failure and disagreement

**When sources conflict:** record every version with its source and date, state which you would act on and why, and mark the row Contradicted. Never silently pick one, and never average two numbers into a third that no source supports.

**When verification is blocked** (paywall, 403, login required, region lock): say so explicitly. Record the attempt, the blocker, and what would resolve it. "I could not verify this" is a valid, complete research output and is always better than a confident guess.

**When a source is undated:** treat it as Unverified regardless of how authoritative it looks. An undated technical page is usually stale.

**When the user supplies a fact** (as with a regional price they can see and you cannot): record it as **Unverified — user-reported**, with the date they said it and a note to confirm at checkout. The user is a good source about their own account, not a citable one.

**Never** fabricate a URL, a version number, a date, or a price. If a specific number is not available, write "not verified" and move on. A missing number is a small problem; a fabricated one is a decision made on fiction.

---

## 5. Checking pricing and limits

For each tool in the stack:

1. Open the official pricing page **from India**, in a normal browser session.
2. Record: plan name verbatim, price as displayed, currency, billing period, whether tax is included.
3. Record the usage limits in the tool's own words. Vague limits ("generous usage") are recorded as vague — do not convert them into numbers.
4. Note regional plans. India-specific tiers exist and are frequently absent from international pages and from third-party summaries.
5. Confirm at checkout before committing. The checkout price is the only Verified price.

Output goes to [BUDGET-POLICY.md](BUDGET-POLICY.md) section 3, with dates.

---

## 6. Checking library freshness

Before proposing any package ([LIBRARY-POLICY.md](LIBRARY-POLICY.md)):

```bash
npm view <package> version time.modified license
```

Then check on the repository: last commit, open issues referencing your framework's current major, whether maintainers reply, and whether a successor exists (`x` superseded by `x-next` is a common and easy-to-miss pattern).

Record in `RESEARCH.md` with the date. Re-verify after 90 days.

---

## 7. Research budget

Research is a real cost. Bound it.

| Question type | Budget |
|---|---|
| A single fact (a price, a version) | 1-2 lookups |
| A comparison (3 options) | 5-8 lookups |
| A landscape survey | 10-15 lookups, then stop and report |

If a question is unresolved after its budget: report what is known, what is not, and what you would need. Do not keep searching. Unbounded research is one of the main ways subscription usage disappears with nothing to show. See [MODEL-ROUTING.md](MODEL-ROUTING.md) section 8.

**Reuse before researching.** Check existing `RESEARCH.md` files from previous projects first. A dated fact from six weeks ago may be good enough, and knowing it exists costs nothing.
