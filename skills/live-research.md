# SKILL: live-research

**Trigger** — a claim depends on the current state of the world: pricing, versions, limits, licences, whether a thing still exists.
**Owner** — Researcher · **Class** — `R1` + `R4`
**Inputs** — open questions from `PROJECT.md`
**Output** — rows in [`RESEARCH.md`](../templates/RESEARCH.md)

Policy: [RESEARCH-POLICY.md](../RESEARCH-POLICY.md). This file is the procedure.

---

## Method

**1. Write the question as a falsifiable claim.** "What does Cursor cost?" is a query. "Cursor's India individual plan is ₹650/month" is a claim that can be checked and dated. Claims are what go in `RESEARCH.md`.

**2. Check existing research first.** Previous `RESEARCH.md` files may already answer it. A 6-week-old dated fact often beats a fresh search, and checking costs nothing.

**3. Set the budget before searching.** One fact: 1-2 lookups. A three-way comparison: 5-8. A landscape survey: 10-15, then stop and report. Unbounded research is one of the main ways subscription usage disappears with nothing to show.

**4. Go to the primary source.** The vendor's own page, the repository, the actual `LICENSE` file, the npm registry. Search engines are for *finding* the primary source, not for being the source.

Skip "Top 10 X in 2026" articles entirely. They are frequently generated, frequently wrong, and carry a current-looking date over stale content. Use them only as a pointer to something primary.

**5. Record immediately, with all four fields.** Claim, date, URL, confidence. A fact held in conversation and written down later loses its source. Confidence levels: [RESEARCH-POLICY.md](../RESEARCH-POLICY.md) section 3.

**6. When sources disagree, record all of them.** Mark the row Contradicted, state which you would act on and why. Never average two numbers into a third that no source supports.

**7. Report what you could not verify.** Paywalls, 403s, region locks, login walls. Record the attempt and the blocker. **"I could not verify this" is a complete, valid output** and is always better than a confident guess.

---

## Specific procedures

**Pricing** — open the official page from your own region, in a normal browser. Record the plan name verbatim, the displayed price, the currency, the period, and whether tax is included. Note that pages localise by IP and third-party summaries almost never get INR right. Only a checkout page is Verified.

**Library status** —

```bash
npm view <package> version time.modified license
```

Then the repository: last commit, open issues naming your framework's current major, whether maintainers reply, whether a successor exists.

**Platform limits** — the vendor's own docs, and prefer their exact words. Vague limits ("generous usage") get recorded as vague; do not convert them into numbers.

**Whether a thing still exists** — check the site loads, the repo is not archived, and there was a release or commit this year. Products get discontinued, renamed, and acquired, and models will confidently describe dead tools.

---

## Done when

Every question is Verified, Reported, Unverified, or Contradicted — with a date and a URL. **No question is left implicitly answered from memory.**

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Answering from memory because it feels obvious | The trigger test: could it have changed, and does being wrong cost anything? |
| Citing a blog post that cites a blog post | Follow to the primary source or mark Unverified |
| Fabricating a plausible version number or price | Never. "Not verified" is the answer. |
| Regional pricing reported as universal | Note the region; only checkout is Verified |
| Research that never ends | Budget set before starting, in step 3 |
| Undated facts entering a document | Four fields or it is not research |
