# Ariadne 2.1 - RC publication

The closure pass that turned a complete, gated release candidate into a published
`2.1.0rc1`. Two product-quality fixes, one merge, one publication, and three real
defects the work surfaced along the way.

Everything below is verifiable. Where something was claimed and turned out to be
false, it says so.

---

## 1. Starting state

| | |
|---|---|
| Branch | `v2/2.1-native-decision-runtime` |
| Starting HEAD | `07a34cb6645ed46f8f1a24d8faab35645f679840` |
| Version | `2.1.0rc1` |
| Gate | green |

Two issues were open:

1. Three spellings of the Decision Runtime identity, so a calibration profile had to
   name the right one by guesswork.
2. `python -m ariadne doctor` did not mention the Decision Runtime at all.

## 2. Runtime identity: one canonical value

### The audit changed the shape of the fix

The brief described three spellings competing for one role. Reading the code showed
they were three different things that happened to share a prefix:

| Spelling | What it actually is | Decision |
|---|---|---|
| `local_bounded` | the runtime *kind* enum, beside `external_bounded` | unchanged |
| `local-bounded-runtime` | the provider *registry* id | unchanged |
| `ariadne-decision-runtime` | the *provenance* identity a profile binds | **canonical** |

Renaming a kind enum or a released registry id to make one word would have broken live
surface for no gain. So only the provenance identity is canonicalised, and the other two
stay exactly where they are.

### The function

`contracts.canonical_runtime_id` maps the two historical spellings onto
`ariadne-decision-runtime` and returns anything else unchanged. It is applied where a
profile is written and where one is matched, so new records carry only the canonical
value and records written during 2.1 development keep working with no operator action.

It is deliberately narrow, and the narrowness is tested rather than asserted:

| Input | Result | Why |
|---|---|---|
| `local_bounded` | `ariadne-decision-runtime` | a name this runtime was called |
| `local-bounded-runtime` | `ariadne-decision-runtime` | its registry id |
| `ariadne-decision-runtime` | itself | already canonical |
| `external_bounded` | unchanged | a different implementation's kind |
| `unknown-runtime` | unchanged | never guess |
| `ariadne-decision-runtime-v2` | unchanged | a future major must not match v1 profiles |

### Calibration compatibility

A profile stored as `local_bounded` matches the canonical runtime. Normalisation is not a
shortcut past the rest of the identity, and each of these is tested to still refuse under
an otherwise-matching alias profile:

```
decision definition   question schema digest   decision-definition digest
question version      implementation          concrete model revision
risk class
```

The decision cache keys on the canonical id. An entry written under an alias simply
misses, which is the safe direction: a conservative miss costs one bounded inference, an
uncertain equivalence costs a wrong answer.

## 3. Doctor integration

`ariadne doctor` now reports the Decision Runtime. It is an adapter over
`api.decision_runtime_health`, not a second health checker: everything runtime-specific
is asked of the runtime's own code.

Four states, and the distinctions matter more than the labels:

| State | Meaning | Effect on exit code |
|---|---|---|
| `OPTIONAL_RUNTIME_UNAVAILABLE` | nothing installed; the shipped default | none |
| `HEALTHY` | installed, manifest readable, smoke answered | none |
| `AVAILABLE_WITH_LIMITATIONS` | installed, smoke did not answer | none |
| `BROKEN` | will not load, or reports unavailable | non-zero |

Three things it deliberately does not say:

**Not "calibrated".** Calibration is its own line counting proven profiles, decision
families and active thresholds. A fresh install reads *healthy and ungated*, which is the
truth. The doctor cannot report calibration because a runtime started.

**Not "verified".** The seed installer pins no digests, so the manifest line reads
*readable; no digests are pinned, so its integrity is undescribed*. Hashing the bytes you
just found describes the installation; it does not verify it.

**Not "broken" for slow.** A smoke that cannot complete is *limitations*. Letting startup
latency decide whether `ariadne doctor` exits non-zero made an unrelated product check
fail under load, which was observed before it was reasoned about.

## 4. Defects the work surfaced

Four, all found by doing the thing properly rather than by looking harder.

**The doctor could not reach the installed engine.** The launcher is one dependency-free
module and does not import the engine, so on a correctly installed product the doctor
reported *"the engine could not be inspected (No module named ariadne_engine)"* - the
exact abstraction leak this pass existed to close.

**Reaching it wrote to the installation.** Importing from an installed runtime dropped
`__pycache__` directories into it, and an installed runtime is verified against its
manifest and immutable by contract, so the next install rejected it:

```
ProductError: The active runtime is damaged: runtime contains files outside its manifest
```

The first guard covered only the import statement. The engine loads submodules lazily -
the runtime health check pulls in the sidecar module on first use - so it had to cover
the whole borrowed window. Bytecode writing is now off for the entire diagnostic.

**The doctor launched a sidecar on every invocation.** About a second per call, which
flaked the distribution suite twice. It now asks the runtime's own code, in-process, in
about a tenth of a millisecond. Process startup is verified where it belongs - the
transport suites and the wheel-install gate - and the output says so rather than implying
it was checked.

**The manifest check validated nothing.** It called `default_manifest()` with a positional
argument and had been failing silently into a warning row. And with no digests pinned the
health record overwrote `UNKNOWN` with `True`, saying a readable manifest was a verified
one - the same mistake the integrity story refuses everywhere else.

## 5. The merge

The public repository is the tag home: `tanishkfr/ariadne` carries the release tags, and
`tanishkfr/ariadne-maintainer` carries none. Public master also carries two commits the
maintainer branch does not:

```
64be6b0  docs: group repository documentation into folders
d1c9a91  Add alternative command syntax for Ariadne
```

Neither touches `src/` or `scripts/`, but the first one moved documentation under
`docs/guides` and `docs/policies`, and five checks opened root paths directly. Each failed
with a `FileNotFoundError` rather than anything actionable. All five now resolve a
document by name through one resolver, so a reorganisation is a layout change and not a
gate failure.

Six markdown links that the move broke are fixed, and the agent-security check asserted
one exact link string - making it a test of directory layout rather than of the
instruction boundary. It now asserts the boundary is declared and the link target exists.

The stage packet specs name `docs/policies/` explicitly, because a packet must know
exactly which file it delivers. That is what a canonical input is for.

## 6. Tests

| Suite | Before | After |
|---|---|---|
| `test-decision-runtime.py` | 469 | **475** |
| `test-decision-runtime-mutations.py` | 31 | **32** |
| `test-engine-core.py` | 578 | 578 |
| `test-decision-mutations.py` | 9 | 9 |
| release subset | 76 | **79** |

New functional coverage: canonicalisation of every spelling and four non-aliases; a
legacy profile matched with each identity field varied in turn; cache-key equivalence;
and the three doctor scenarios with the three honest manifest states.

New mutations, all caught:

```
remove runtime canonicalization entirely
canonicalise every string, including unknown runtimes
let a doctor skip the Decision Runtime entirely
make an absent optional runtime fatal
let doctor call an unprofiled runtime calibrated
hide a broken runtime behind a healthy report
make doctor launch a sidecar it can then hang on
```

The last one exists because the sixth was written first and *survived*: adding a call to
a function that did not exist raised a `NameError` that the surrounding handler turned
into a warning, so nothing observable changed. A mutation that survives is not a caught
mutation.

## 7. RC smoke

Run from a clean virtual environment outside the checkout, against the installed wheel
and the installed runtime bundle.

| | Scenario | Result |
|---|---|---|
| S1 | install, then doctor with no runtime | healthy; runtime *not installed (optional)*; no problem row |
| S2 | install the runtime, then doctor | healthy; manifest undescribed; smoke 0.07ms |
| S3 | no calibration profile | answered; no threshold invented |
| S4 | profile with an unreachable threshold | `refused` / `BELOW_MIN_CONFIDENCE`; class `UNKNOWN`; escalated; candidate kept; authority `none` |
| S5 | profile the answer clears | `answered`; `IMPLEMENTATION_FAILURE`; no escalation |
| S6 | legacy alias profile | stored canonically; matches at the same revision; refuses at another |
| S26 | shadow lifecycle | effect `none`; authority `none`; no problems |
| S27 | promotion lifecycle | `UNTESTED -> SHADOW -> EVALUATED -> ELIGIBLE -> ACTIVE -> SUSPENDED`; selection returns to `SHADOW` |
| S28 | cache vs a new threshold | answered before, `refused` after - the cache did not bypass it |

A real local bounded inference through the sidecar subprocess:

```
runtime        : local_bounded, cpu
implementation : ariadne-reference-bounded ar-206-reference-1
question       : failure-classification v1 (ChoiceDecision, 7 answers)
answer         : IMPLEMENTATION_FAILURE
confidence     : 0.981576 (provider probability - uncalibrated)
latency        : 0.48 ms
```

This is a smoke test, not calibration evidence. It writes nothing and no profile is
created from it.

## 8. Adversarial findings

Nine attempts, all refused:

| Attempt | Result |
|---|---|
| unknown runtime alias becomes canonical | preserved verbatim |
| legacy alias lets a wrong revision match | refused |
| runtime alias change hits stale cache | safe miss |
| doctor downloads a model | it does not |
| doctor hangs on a broken sidecar | no process launch at all |
| doctor reports healthy despite a failed smoke | `AVAILABLE_WITH_LIMITATIONS` |
| doctor reports calibration with zero profiles | separate line, always counts |
| absent optional runtime makes Ariadne unhealthy | no problem row |
| a traceback reaches the user | never; every failure is caught and named |

## 9. Publication

Recorded in the closure report rather than here, because this document is committed and
the commit cannot contain its own hash.

## 10. Remaining limitations

1. **No calibration profile ships.** A fresh install answers every bounded question
   ungated. Correct - a threshold requires measurement - and the doctor says so plainly.
2. **The reference engine is rule-derived, not trained.** Strong on enumerated structure,
   weak on prose.
3. **No automatic training, and no guarantee every decision family is calibrated.**
4. **Local runtime performance is hardware-dependent.** The 0.48 ms figure above is one
   machine, one question.
5. **`python -m ariadne doctor` does not launch the sidecar**, so it verifies the engine
   and the manifest rather than process startup. Process startup is covered by the
   transport suites and the wheel-install gate.

Nothing here is a release blocker, and nothing is a promise that 2.1.0 will keep.
