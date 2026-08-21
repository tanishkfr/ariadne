# RESEARCH POLICY

How the system tells a fact from a memory.

**A model's training data is a snapshot of the past presented with the confidence of the present.** Anything that changes over time gets looked up, dated, and sourced — or explicitly marked unverified.

S2 is **conditional**. Run it only when a fact about the world blocks a decision. Output: [templates/RESEARCH.md](templates/RESEARCH.md).

---

## 1. What requires verification

**Always. Never answer from memory:**

pricing, plans, regional tiers, limits · which models exist and their capabilities · library versions, last release, maintenance, framework compatibility · breaking changes and deprecations · platform rules (deploy limits, build minutes, social character limits) · licences (font EULAs, package licences, asset terms) · "best current" anything · **whether a thing still exists** — products get discontinued, renamed, and acquired, and models will confidently describe dead tools.

**Safe from memory:** language and CSS fundamentals · design principles, typography, colour theory · algorithms · anything in this repository · **anything a command answers** — run the command instead, it is cheaper and definitive.

**The trigger question:** *could this have changed since training, and would being wrong cost anything?* Both yes means verify.

---

## 2. Procedure

**1. Write the question as a falsifiable claim.** "What does Cursor cost?" is a query. "Cursor's India individual plan is ₹650/month" is a claim that can be checked and dated. Claims are what go in `RESEARCH.md`.

**2. Check existing research first.** Previous `RESEARCH.md` files may already answer it. A six-week-old dated fact often beats a fresh search, and checking costs nothing.

**3. Set the lookup budget before searching.**

| Question | Budget |
|---|---|
| A single fact | 1-2 lookups |
| A three-way comparison | 5-8 |
| A landscape survey | 10-15, then stop and report |

Unbounded research is one of the main ways subscription usage disappears with nothing to show ([MODEL-ROUTING.md](MODEL-ROUTING.md)).

**4. Go to the primary source.** Search engines are for *finding* it, not for being it.

**5. Record immediately**, with all four fields. A fact held in conversation and written down later loses its source.

**6. When sources disagree, record all of them.** Mark the row Contradicted, state which you would act on and why. **Never average two numbers into a third that no source supports.**

**7. Report what you could not verify.** Paywalls, 403s, region locks. Record the attempt and the blocker. **"I could not verify this" is a complete, valid output** and is always better than a confident guess.

---

## 3. Source ranking

Prefer a lower number when sources disagree.

| # | Tier | Trust |
|---|---|---|
| 1 | **Official primary** — the vendor's own page, the repository, the actual `LICENSE` file | Verified |
| 2 | **Machine-readable registry** — npm, GitHub API, bundlephobia | Verified |
| 3 | **Official secondary** — changelog, release notes, status page | Verified / Reported |
| 4 | **Reputable independent** — established publications, maintainer posts | Reported |
| 5 | **Community** — Stack Overflow, Reddit, issues | Useful for *whether a problem exists*, not for what is true |
| 6 | **SEO content** — "Top 10 X in 2026" listicles | **Pointer only. Never evidence.** |

Tier 6 deserves naming: frequently generated, frequently wrong, and carrying a current-looking date over stale content. Use one only to find something primary.

---

## 4. Recording

Four fields, always: **claim · date · source URL · confidence.** Missing one means it is not research.

| Confidence | Means |
|---|---|
| **Verified** | Seen on an official primary source today |
| **Reported** | Consistent across two or more independent secondary sources |
| **Unverified** | Single weak source, user-reported, or verification blocked |
| **Contradicted** | Sources disagree; all versions recorded |

**Freshness:** pricing and limits go stale after **30 days**; library status after **90**. Re-verify before relying on an old row. Do not delete superseded rows — date them and keep the history, because knowing a number changed is itself useful.

**An undated source is Unverified** regardless of how authoritative it looks.

**A user-supplied fact** (a regional price they can see and you cannot) is **Unverified — user-reported**, with the date, and a note to confirm at checkout. The user is a good source about their own account, not a citable one.

**Never fabricate** a URL, a version number, a date, or a price. A missing number is a small problem; a fabricated one is a decision made on fiction.

---

## 5. Specific procedures

**Pricing.** Open the official page **from your own region**, in a normal browser. Record the plan name verbatim, the displayed price, currency, period, and whether tax is included. Pages localise by IP and regional tiers frequently never appear on international pages. **Only a checkout page is Verified.** Third-party pricing summaries are Reported at best and almost never get INR right.

**Library status.**

```bash
npm view <package> version time.modified license
```

Then the repository: last commit · open issues naming your framework's current major · whether maintainers reply · whether a successor exists (`x` superseded by `x-next` is common and easy to miss).

**Platform limits.** The vendor's own docs, in their exact words. Vague limits ("generous usage") get recorded as vague — do not convert them into numbers.

**Whether a thing still exists.** Site loads · repo not archived · a release or commit this year.

---

## 6. Design and visual research

Different rules — this is inspiration, not fact, so mechanism matters more than freshness.

Studio and designer sites **live, not screenshot galleries**. Print, editorial, packaging, signage, and film titles are **often better sources than other websites**, because the mechanism has to survive translation to a different medium — which is exactly the test that separates a mechanism from a surface.

Standing set: [references/visual-references.md](references/visual-references.md). Method: [skills/reference-analysis.md](skills/reference-analysis.md).

**Warning:** inspiration galleries homogenise. Everything on them looks like everything else on them, because one taste curated it. If every reference comes from the same gallery, you will produce that gallery's house style.
