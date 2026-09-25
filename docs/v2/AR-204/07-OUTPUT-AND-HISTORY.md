# AR-204 — Output Externalization and History

The two places where a long run gets expensive, and the evidence rule that governs
both.

## 1. The defect AR-204 found

The runtime already hashes every validation command's stdout and stderr:

```text
"stdout_sha256": hashlib.sha256((completed.stdout or "").encode("utf-8")).hexdigest()
```

That is a digest with no artifact behind it. When a build or test run produces a
megabyte of diagnostics, the run keeps a 64-character fingerprint and discards
the diagnostics, so a later reader can prove the output existed but cannot read
it. AR-204 treats that as an evidence defect rather than a token problem.

## 2. Three states, one threshold

`artifacts.externalize` classifies an output before it decides anything:

| State | When | Model-facing view |
| --- | --- | --- |
| `fully_inline` | at or below the threshold | the output itself, unchanged |
| `inline_excerpt_plus_artifact` | above the threshold, moderate size | head and tail excerpts plus a reference |
| `artifact_only` | far above the threshold | metadata, digest and a retrieval handle |

The default threshold is 8,192 bytes. It is defensible rather than invented: the
fixture packets run 16-50 KB, and the AR-203 verification artifacts recorded in
`docs/v2/AR-203/08-TEST-RESULTS.md` run below 12 KB, so 8 KB sits below the size at
which a reference starts paying for its indirection and above the size at which
inlining is free. The value is configurable and the threshold is a setting, not a
law.

## 3. What is preserved

`artifacts.externalize` writes the complete bytes to
`evidence/artifacts/<sha256>.log` and returns a record naming the tool, the
command, the source execution, the task, the digest, the size, the creation time,
a deterministic summary and the excerpts. The model-facing block from
`artifacts.render_for_model` carries the path, the digest, the size and the
excerpts, and states how many bytes the model view omits. The full artifact is not
a cache: it is the evidence.

## 4. Retrieval that refuses

`artifacts.retrieve` re-hashes the file before returning it. A missing artifact or
a changed digest is a refusal, not a warning, which is invariance 43 as an
executable rule. The benchmark asserts both directions: the tampered artifact is
refused and the restored one verifies.

A verification can be built against the artifact at `OBSERVED` and its freshness
is dependency-bound to the digest, so changing the artifact makes the verification
stale through the ordinary AR-203 rule rather than through a special case.

## 5. Runtime integration

`validate_worker` now routes each captured stream through
`externalize_validation_output`. Small output is untouched: no file, no extra
field, no behaviour change. Large output gains the artifact plus additive fields
in `validation.json`, and a reference is appended to the run state's `artifacts`
collection under a declared bound. An engine check and a benchmark case both
exercise the seam: the complete bytes are on disk with a correct digest, and a
small output is left alone.

`output_externalization` defaults to `threshold`. It is the one default-on setting
in the efficiency policy, and it qualifies because it only changes *storage*: the
digests are unchanged and no information is discarded.

## 6. History, measured before compacted

`history.history_economics` reports total bytes, protected bytes, bytes per turn,
growth per turn, duplicate groups, duplicate bytes and repeated-source bytes. The
measurement exists so that "the history is long" is never on its own a reason to
compact anything.

## 7. Compaction that cannot lose the run

`history.compact` is structural. A protected entry — current task state,
unresolved work, a decision, an authorization, an evidence reference, a failed
approach, the current revision, the verification state — is carried verbatim. An
unprotected entry becomes one deterministic line with its kind, turn, size, digest
and first line. An exact duplicate is marked as one rather than repeated.

Before any of that, the complete original history is written to a JSONL archive
whose digest is recorded, and `history.retrieve_history` re-hashes it before
returning it. A plan that would omit a protected entry, or that claims a summary
replaces the history, is refused by `history.compaction_problems`. This is
invariance 44 with both a mutating test and a mutation test behind it.

## 8. State of the flag

`compaction` defaults to `off` and `history_format` defaults to `legacy`. Nothing
in a normal run is compacted. The strategy is implemented, measured and reversible,
and the decision to enable it belongs to a control-versus-candidate experiment with
a live model, which this milestone did not run.
