# SKILL: adversarial-review

**Trigger** — a change is complete and a review boundary is retained; the reviewer must not be the author.
**Owner** — an independent reviewer with the isolated packet; never the implementing session
**Inputs** — the isolated review packet: the change, the stated requirements, and the evidence — nothing about how the work was done
**Output** — ranked falsification attempts with what actually happened, or an explicit statement that none succeeded

Review here is an attempt to break the change, not a summary of it. Confirming
that the code looks reasonable is the weakest possible review; this method spends
its effort where the change is most likely to be wrong.

## Method

1. **Read the requirements as claims.** Each acceptance criterion is a claim the
   change must make true. List them before reading the diff, so the diff cannot
   redefine them.
2. **For each claim, construct a falsification attempt.** A concrete input, state,
   or sequence that should make the claim false if it is false. Write the attempt
   down before running it; a review that only runs whatever is convenient is a
   tour, not a test.
3. **Attack the boundaries.** Empty and missing inputs, the second call, the
   concurrent call, the error path, the very large and the very small, state that
   arrives out of order, and the case where the dependency is unavailable.
4. **Attack the evidence.** Is each claim backed by something that could have
   failed? A test that passes on any input, a screenshot that predates the change,
   a citation that does not say what it is quoted for — these are gaps, and they
   rank above style opinions.
5. **Rank findings by consequence, not by ease.** A wrong result on a normal input
   outranks a tidiness issue in a rarely used branch. Each finding names the claim
   it breaks, the attempt that exposed it, and the observed result.
6. **State the residual uncertainty.** What was not attempted and why is part of
   the review. A clean review is "these attempts failed", never "this is correct".

## Recording

Claims, attempts, observed results, ranked findings, and the residual uncertainty.
The reviewer's own identity and independence are workflow facts recorded by the
engine, not assertions in the review text.

## Stop conditions

- The reviewer authored the change, or the review context leaks the build
  history: stop; the review is void and must run independently.
- The packet's evidence is missing rather than merely weak: report it as an
  evidence gap instead of reviewing around it.
- A finding implies a change to the approved direction: raise it to the human
  decision rather than accepting or fixing it inside the review.
