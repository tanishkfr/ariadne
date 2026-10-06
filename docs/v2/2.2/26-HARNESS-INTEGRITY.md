# 26 — Harness Integrity

## The two failures AR-222 found

1. **Record lookup returned copies.** `by_id()` handed back a detached `dict`, so every write
   through that handle vanished while the caller still received a plausible value. Scope
   enforcement and no-self-review guarantees became **no-ops that looked like passes**.

2. **Live mutation remained applied during `git add`.** A mutated engine could be committed as
   though it were the real one — and the corruption was invisible to `git diff` when the file
   was untracked.

Both are structural, not incidental, so both are fixed structurally.

## Record identity and mutation semantics

AR-222 already documented each `by_id()` as returning the live record, which is correct and
not enough: a docstring is a convention, and a convention is one edit away from a copy.

```text
def by_id(state, evidence_set_id):
    """The stored manifest, not a copy.

    ``mark_rerendered`` writes through this handle, so a defensive copy would make the
    closure a silent no-op that still returns a plausible record.
    """
```

AR-222D adds the regression test that makes the docstring load-bearing:

```text
record lookup returns detached copy where canonical mutation required
```

It mutates through `critique.by_id`, `evidence.by_id`, `refinement.by_id` **and**
`render.by_id`, and asserts each write landed in canonical state. `render.by_id` had **no**
docstring at all — it keys on `evidence_id` (AR-202D's field) rather than
`evidence_set_id` (AR-222's), which is exactly the sort of ambiguity that lets a caller
assume the wrong contract.

Scope enforcement is likewise tested against the engine's own `refinement.record_change`,
not a local reimplementation:

```text
scope enforcement mutation becomes a no-op is caught
```

The earlier version of that test recomputed the scope comparison itself — a test of the test
file. The mutation it was written for could be applied and the case still passed. That is what
the mutation harness is for, and it is why `M21` and `M22` exist.

## One ledger, many harnesses

AR-222's fix for a collision between two harnesses sharing a marker path was to give them
*different* paths. That solved the crash and left the real problem untouched: **no other
process could ask whether the repository was mid-mutation.**

`scripts/harness/mutation_ledger.py` is the shared answer. One registry, many harnesses, one
query:

```text
.ariadne-mutation-active.json    which harnesses currently hold the tree mutated
```

A keyed registry of entries — not one harness's shape — because the AR-222 lesson was that
whoever assumes it owns a single-object marker misreads the other one's record and crashes.
An entry nobody recognises is simply another harness's business.

The per-harness markers and stashes stay exactly as they were: they hold the bytes and remain
the recovery path. The ledger is **state**, added beside them, and state is what a commit has
to refuse on.

## Fail closed

```python
assert_no_active_mutation(repo, operation="commit")
```

Refuses when the tree is mid-mutation. Called by commit, release and gate paths. `git diff` is
not a substitute: untracked files and gitignored fixtures do not appear in it, and this
repository has both — `node_modules/` and `.ariadne-mutation-*` are ignored.

Refused for: `commit`, `release`, `tag`, `publish`.

## Unknown is not clear

An unreadable ledger is not an empty ledger:

```python
"active": bool(entries) or not known,
"invariant": "an unknown mutation state is an active mutation state",
```

Four corrupt ledger shapes (`{not json`, `{}`, `{"harness": "x"}`, `null`) all fail closed.
The alternative is the worst possible one: a corrupted sentinel that reads as "nothing is
mutated" is a sentinel that has silently stopped working.

A **stale** entry — one whose owning pid is gone — is reported rather than dropped, because a
killed harness leaves an entry by definition and that is exactly the case worth surfacing:

```text
the mutation ledger is not clear ... harnesses: dead-harness. STALE (owning process is gone,
recovery required): dead-harness
```

On Windows, liveness is decided by `GetExitCodeProcess` + `STILL_ACTIVE`, **not** by
`OpenProcess` succeeding. `OpenProcess` succeeds for an exited process whose handle is still
openable, and can succeed briefly after a kill. Getting this wrong in the permissive
direction means a killed harness looks live, its entry is never reported stale, and recovery
is never offered — the precise failure the module exists to prevent.

## Transactional mutations

```text
capture bytes and record the expected state   -> before anything is edited
write the stash to disk                        -> so a killed process is recoverable
register in the ledger                         -> so anything else can see the state
apply the mutation                             -> the only mutating step
yield
restore bytes, clear stash, deregister         -> in a finally
verify restoration                             -> and report it
```

The order is the whole point. The stash is on disk *before* the edit, so a kill at any moment
leaves either a recoverable stash or an active entry — never a mutated file with no record.

`finally` covers success, failure, exception and timeout. It does **not** cover a process
killed from outside, which is why the stash is on disk and the ledger entry names the pid.

## Restoration verified against actual expected state

```text
tracked file digests
relevant untracked fixture inventory   (digested, not sized)
mutation-state sentinel
```

`git diff == empty` satisfies none of these independently: it is equally consistent with
restored, never-mutated, and a mutation to a path git does not track.

The inventory is **digested** rather than sized — a finding from the adversarial suite. A
mutated fixture of exactly the same length is the easiest corruption to miss, and it is
invisible to a size check:

```python
target.write_text('{"name": "fixture"}\n')
# ... a mutation writes '{"name": "MUTATED"}\n' -- 19 bytes either side
assert not verify_restoration(expected)["restored"]
```

Restoration reports three states, not two:

```text
YES    proven restored
NO     proven not restored
UNKNOWN could not be determined
```

An unreadable sentinel routes to `UNKNOWN` rather than `NO`, because the two deserve different
answers: `NO` says *run recovery*, `UNKNOWN` says *find out what happened first*.

## Test inventory integrity

AR-222's cleanest argument for mutation testing:

> During the containment-test rewrite, line-range surgery swallowed
> `a_launch_argument_may_not_carry_a_nul_or_an_implausible_length`. The suite went green —
> 86/86 — and only the mutation *"browser launch argument injection"* surviving revealed
> that a real guarantee had lost its coverage.

A test disappeared. The suite still reported a count, and the count went *down* and nobody
was watching.

Two mechanisms, because the two failures are independent:

**37 named critical guarantees** (`test_inventory.CRITICAL_CASES`) across nine groups —
render-and-capture identity, critique independence, record identity semantics, repair lineage,
mutation harness integrity, design specificity grammar, source ecosystem, user autonomy,
Beacon negative case. A named guarantee that vanishes is caught by name regardless of the raw
count.

**Recorded floors per suite** (`test_inventory.SUITE_FLOORS`) catch the unnamed losses no
manifest can enumerate. A count can fall because a case was deleted, renamed or merged — only
the first is a defect, and all three are worth knowing about.

### An unparsed summary is an unenforced floor

The most instructive bug in this phase, found by the gate itself. Two suites print
`N/N passed` without a `PASS` prefix. The inventory understood only the prefixed form, so it
reported `0/0` — which read as *"no floor violation"* and **passed silently**:

```text
the mutation ledger is still active ...        # the same shape, one level up
```

```python
if summary["kind"] == "narrative" or not summary["total"]:
    unparsed.append({... "an unparsed summary is an unenforced floor, not a satisfied one"})
```

A summary the checker cannot parse is a gate it cannot enforce, so it is reported rather than
skipped. The same applies to the regex flags: without `re.MULTILINE`, `^` matches only the
start of the output, so a `PASS 87/87` on the *last* line after ninety results is invisible.

### A surviving mutation is a failure to investigate

`survivor_report()` classifies every survivor as one of:

```text
missing coverage    no case asserts the behaviour this mutation removed
broken mutation     the mutation did not actually change the behaviour
invalid invariant   the code's assumption is wrong and the tests encode it
```

and lists the forbidden responses explicitly:

```text
weaken the mutation until it dies
delete the mutation to restore green
raise the recorded floor to match the new lower count
```

Restoring green by making a mutation stop biting destroys the only evidence that one of those
three is true. The AR-222D mutation run found **nine survivors on its first pass**; every one
was investigated, and all nine were real coverage gaps in the test suite rather than
mutations to be softened.

## Long gate execution and no blind re-running

`run-suites.ps1` records suite / start / finish / exit state / duration for every suite. The
rule it exists to enforce:

> **A truncated tool call must never be read as "suite passed" or "suite still running".
> Unknown stays unknown.**

This was not hypothetical. AR-222D's own baseline sweep was killed by a tool timeout
mid-run, and the honest resolution was to diagnose before re-running — which turned out to
matter, because the next diagnostic found something else entirely:

**A real incident, recorded because it is the argument for this whole document.**

`test-decision-runtime.py` first reported **509/510**, failing *"the suite writes nothing into
the repository"*. The assertion was accurate and the **diagnosis was wrong**: I had launched
the AR-220 and AR-221 *mutation* suites in parallel with it. Those suites deliberately edit
`src/**/*.py`, so decision-runtime correctly observed source files changing underneath it and
blamed itself.

Re-run serially: **PASS 510/510**. No code defect.

That is exactly the failure AR-222 found — a mutated tree, recorded as though it were the real
one — and the only signal available at the time was a false accusation aimed at the wrong
suite. With a sentinel it becomes *"a mutation was active, here is which harness"*, and the
commit is refused rather than the diagnosis being wrong.

Neither mutation harness may now start while another holds the tree:

```text
another harness holds the tree mutated: ar222-mutations (M07). Two mutation harnesses at
once make each other's results meaningless, so this run will not proceed.
```

## Concurrency, recorded

Mutation harnesses are **serial**, always. Suites that assert repository cleanliness must not
run concurrently with a mutation harness. Both AR-221 and AR-222 harnesses now register in
the shared ledger; the AR-222D harness uses the full transactional context manager.

## The gate

```text
python scripts/ar222d-gate.py
```

```text
== 1. mutation state ==      fail closed if the tree is mid-edit, by us or by a killed harness
== 2. test inventory ==      named critical guarantees present, no suite below its floor
== 3. AR-222D suites ==      the design grammar, its mutations, and the adversarial review
```

Distinct exit codes so a caller can tell them apart: `1` mutation active, `2` inventory loss,
`3` suite failure.

## See also

- [27 — Adversarial Review](27-ADVERSARIAL-REVIEW.md)
- [28 — AR-222D Results](28-AR-222D-RESULTS.md)
