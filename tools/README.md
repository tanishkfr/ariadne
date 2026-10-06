# Operator tools

Scripts that a person runs deliberately, by hand, outside the Ariadne workflow.

These are **not** release tooling and are **not** part of the runtime. That
distinction is load-bearing:

- `scripts/` is covered by the `distribution.release-tooling-offline` benchmark,
  which asserts that no shipped script imports a network client. A release must
  never depend on the network, so nothing that reaches the network belongs there.
- `src/ariadne_engine/` is the engine: import-safe, offline, standard library only.

## `record-getdesign-fixture.py`

Performs the AR-220 live retrieval once and freezes it as a regression fixture.

```bash
python tools/record-getdesign-fixture.py --slugs linear.app cursor warp vercel cohere
```

It is the **only** part of Ariadne that contacts getdesign.md, and it does so under
the retrieval policy recorded in `getdesign.RETRIEVAL_POLICY`: targeted single-file
HTTPS, no crawling, no sitemap walking, no link following, no enumeration, no
authenticated endpoint, and a bounded request budget.

Running it is a manual decision. Nothing in a normal Ariadne run invokes it, and no
test depends on it — the regression suite reads the recording it produces, which is
the point: a suite that fetched live would be a different test each time it ran.

It writes into `src/ariadne_engine/design_reference/fixtures/getdesign-md/`,
retrieving the documents from the maintainers' public MIT-licensed repository
(`VoltAgent/awesome-design-md`) rather than from the catalog, whose own DESIGN.md
download is sign-in gated and whose Terms of Service prohibit automated scraping.

After refreshing the corpus, re-run the AR-220 suite:

```bash
python scripts/test-design-reference.py
python scripts/test-design-reference-mutations.py
```