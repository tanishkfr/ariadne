# RESEARCH SOURCES

Where to look, ranked by how much to trust it.

Policy: [RESEARCH-POLICY.md](../RESEARCH-POLICY.md). Method: [live-research](../skills/live-research.md).

---

## The ranking

Prefer a lower number when sources disagree.

| # | Tier | Examples | Trust |
|---|---|---|---|
| 1 | **Official primary** | The vendor's own pricing page, the package repository, framework docs, the actual `LICENSE` file | Verified |
| 2 | **Machine-readable registry** | npm registry, GitHub API, bundlephobia | Verified |
| 3 | **Official secondary** | Vendor changelog, release notes, status page, official blog | Verified / Reported |
| 4 | **Reputable independent** | Established technical publications, maintainer posts, conference talks | Reported |
| 5 | **Community** | Stack Overflow, Reddit, Discord, GitHub issues | Useful for *whether a problem exists*, not for what is true |
| 6 | **SEO content** | "Top 10 X in 2026" listicles, aggregator blogs | **Pointer only. Never evidence.** |

Tier 6 is worth naming explicitly: these are frequently generated, frequently wrong, and carry a current-looking date over stale content. They are useful for one thing — finding out that a primary source exists. Then go to it.

---

## Commands

```bash
npm view <package> version time.modified license
npm view <package> versions --json      # release cadence
```

Then check the repository: last commit, open issues naming your framework's current major version, whether maintainers reply, and whether a successor exists — `x` superseded by `x-next` is a common and easy-to-miss pattern.

---

## Pricing

**The single most error-prone category**, and the one where being wrong costs money.

1. Open the official pricing page **from India**, in a normal browser session.
2. Record the plan name **verbatim**, the displayed price, the currency, the billing period, and whether tax is included.
3. **Only a checkout page is Verified.** Pricing pages localise by IP, regional plans exist that never appear on international pages, and third-party summaries almost never get INR right.

Third-party pricing articles are Reported at best. This is not pedantry — during the construction of this system, the official ChatGPT pricing page returned HTTP 403 and the Cursor India plan was not visible on the international page at all. Both gaps are recorded in [BUDGET-POLICY.md](../BUDGET-POLICY.md) rather than papered over with a plausible number.

---

## Design and visual research

Different rules — these are for *inspiration*, not fact, so freshness matters less and mechanism matters more.

- Studio and designer sites directly. The live site, not a screenshot gallery.
- Awards and curation sites, for breadth.
- Print, editorial, packaging, signage, and film titles — **often better sources than other websites**, because the mechanism has to survive translation to a different medium, which is exactly the test that separates a mechanism from a surface.

Your standing set: [visual-references.md](visual-references.md).

**Warning:** design-inspiration galleries produce a homogenising effect. Everything on them looks like everything else on them, because they are curated by the same taste. If every reference comes from the same gallery, you will produce that gallery's house style.

---

## Recording

Four fields, always: **claim, date, source URL, confidence.** Anything missing one is not research — it is memory.

Format: [templates/RESEARCH.md](../templates/RESEARCH.md).

**Freshness:** pricing and limits go stale after 30 days; library status after 90. Re-verify before relying on an old row. Do not delete superseded rows — date them and keep the history, because knowing a number changed is itself useful.

---

## Budgets

| Question type | Lookups |
|---|---|
| A single fact | 1-2 |
| A three-way comparison | 5-8 |
| A landscape survey | 10-15, then stop and report |

Set the budget **before** searching. Unbounded research is one of the main ways subscription usage disappears with nothing to show for it ([MODEL-ROUTING.md](../MODEL-ROUTING.md) section 8).

**Reuse before researching.** Check existing `RESEARCH.md` files from previous projects first. A dated fact from six weeks ago may be good enough, and finding out costs nothing.
