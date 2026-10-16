# SKILL: blast-radius

**Trigger** — a change is planned in shared code, a public interface, a schema, or anything with more than one consumer.
**Owner** — the worker making the change, before the first edit
**Inputs** — the identified change surface, the repository, search access
**Output** — the named consumers of the surface, the behaviours at risk, and the regression checks that cover them

Scope is discovered, not assumed. This method finds who depends on the thing you
are about to change so the change is bounded by evidence instead of optimism.

## Method

1. **Name the surface exactly.** Write down the symbol, file, route, type, or
   contract being changed. "The parser" is not a surface; `parse_header()` in
   `src/parser.py` is.
2. **Search for every way it is reached.** Callers by name, imports, re-exports,
   string references in configuration or tests, generated artifacts, and documented
   usage. Record the search you ran — the query is the evidence, not your memory of
   the code.
3. **Classify each consumer.** Direct callers change with the surface. Indirect
   users (serialised output, stored data, external consumers, scripts) survive the
   change only if the contract does; list them separately.
4. **Name the behaviours at risk.** For each consumer, the property that breaks if
   the change is wrong: a return shape, an ordering guarantee, an error contract, a
   timing assumption. A risk without a behaviour is a worry, not a finding.
5. **Choose the smallest safe change.** If a compatible extension covers the
   surface, prefer it over a breaking rewrite; the consumers you found decide which
   is which.
6. **Bind the risks to checks.** For every risk, name the existing test that covers
   it or add one. If neither is possible, record that as an open risk with the
   reason.
7. **Re-run the searches after the change.** A consumer list is valid for one
   revision; confirm nothing new depends on the surface before you close.

## Recording

Write the surface, the exact searches, the consumer table, the risk list, and the
checks that cover each risk. Consumers you could not rule out stay in the record as
unresolved, never as silently-empty.

## Stop conditions

- The surface has no searchable name (reflection, dynamic dispatch, generated
  code): record the blind spot and the narrower check you used instead.
- A consumer is outside this repository: stop before the breaking change and raise
  the compatibility decision to the human.
- The risk list cannot be covered by any available check: record it and let the
  review boundary weigh it.
