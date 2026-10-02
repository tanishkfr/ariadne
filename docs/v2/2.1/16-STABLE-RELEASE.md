# Ariadne 2.1.0 - Stable release

The record of promoting `2.1.0rc1` to stable: what was audited, what was fixed, what
the real-world run found, and what is still not proven.

---

## 1. Starting point

```
tag       v2.1.0rc1
commit    01c959ab85584ec20863690136a53817e80a3b6a
gate      green (12/12)
```

The RC was published, downloaded, clean-installed and smoked independently. Stable did
not inherit an untested candidate; it inherited a verified one.

## 2. Resolver audit

The RC merge introduced a document resolver so that release checks could find documents
after the public repository moved them into `docs/guides` and `docs/policies`. It was
**first-match-wins with no containment check**, and both of those turned out to matter.

**Traversal.** `resolve_document("../INSTALL.md")` returned `"../INSTALL.md"` and pointed
at a real file one directory above the checkout. `resolve_document("../../VERSION")`
climbed out of the repository and back in. An absolute Windows path was returned verbatim.
A release gate that can be pointed outside its own tree by a document name is not a gate.

**Silent shadowing.** First-match-wins is worse than it looks. A document left at the
root after moving into `docs/guides` is not a harmless duplicate: it shadows the current
copy for every check that resolves by name, and each of them reports success while
validating stale text. Nothing in the RC would have said otherwise.

**The resolver now requires exactly one safe match:**

| Reason | Meaning |
|---|---|
| `UNSAFE_DOCUMENT_NAME` | absolute, empty, leading separator, or containing `..` |
| `DOCUMENT_NOT_FOUND` | no approved directory holds it; the refusal names where it looked |
| `AMBIGUOUS_DOCUMENT` | more than one does, and the refusal names both |

Approved roots are an explicit four-entry list searched without recursion, so it cannot
reach `.git`, `dist`, `src`, a benchmark output tree or a mount beside the checkout. The
joined candidate is asserted to be inside the repository rather than assumed to be.

What it is not: a sandbox. The checks already read ordinary repository files such as
`references/capabilities.json`. What it refuses is a name that leaves the repository.

**Stage packets are untouched.** A canonical input names an exact path because a packet
has to know precisely which file it delivers; only the release checks resolve by name.
That distinction is now asserted by a test, so a future edit cannot quietly blur it.

## 3. Release authorization semantics

`RELEASING.md` said *"Public naming, tagging, pushing and publishing remain human
actions."* That stopped being true when an authorized agent workflow published the RC,
and it would have misdescribed what happened. It now says what is required:

> Public naming, tagging, pushing and publishing require explicit human authorization.
> Authorized release automation, or an agent working under such an authorization, may
> perform those actions within the approved release scope and only after the release
> gate passes.

Authorization is not keystrokes, and the boundary is not weakened:

```
authorized: publish v2.1.0rc1

does NOT authorize: publishing v2.1.0, publishing to PyPI, deleting a release,
                    force-pushing, rewriting history, moving a published tag
```

A new release needs a new authorization, and absence of one reads as "not authorized".
The gate is not waivable by authorization, and no emergency override was added.

## 4. Runtime identity wording

The RC notes said three spellings were "read as aliases", which reads as three
equivalent global names. They are not. `ariadne-decision-runtime` is the canonical
**provenance** identity; `local_bounded` and `local-bounded-runtime` normalise into it
**only when read in a provenance or calibration context**, and their own meanings are
untouched - `local_bounded` remains the runtime-kind enum, `local-bounded-runtime`
remains the provider registry identifier. No enum or identifier was renamed, and no
migration is required.

## 5. Real-world shadow evaluation

An isolated project (`widgetco`: a renderer, a validating theme module, a test, a
project document), 19 genuinely distinct real bounded decisions across all four decision
families, each one something that actually happened to that project, asked through the
four real integration entry points. Nothing about the runtime or the policy path was
mocked.

| Family | Decisions | Answered | Refused |
|---|---|---|---|
| `failure-classification` | 10 | 10 | 0 |
| `review-escalation` | 3 | 0 | 3 |
| `evidence-relevance` | 4 | 4 | 0 |
| `route-family` | 2 | 2 | 0 |

Latency per decision: min 1.65 ms, median 2.02 ms, max 3.66 ms. Every record carried its
full identity - family, question id and version, definition digest, projection digest,
provider, implementation, model revision, contract version.

**Shadow safety held completely.** 19 shadow records; 0 with a non-`none` execution
effect; 0 with a non-`none` authorization effect; 0 decisions acted on; every probability
a provider probability; 0 records labelled calibrated; no isolation problems; no errors.

**19, not 20-50.** The brief suggested a range and said to report the actual count
rather than manufacture copies. It is limited by how many distinct decisions a four-file
project produces, and padding it with repetitions would have added no evidence.

## 6. Two findings, recorded rather than smoothed over

**The failure classifier returned the same answer at the same confidence for ten
genuinely different real failures.** A passing suite, a `NameError`, a missing module, a
type error, a syntax error, a missing interpreter, a missing package, an allocation
ceiling, a slow operation and a successful import all came back as
`IMPLEMENTATION_FAILURE` at `0.198965` - the *identical* value to six figures.

This is the reference engine's documented weakness meeting reality: it is strong on
enumerated structure and weak on prose, and real build output is prose. It is a
limitation, not a defect - the runtime abstains rather than guesses when it has no family,
and its answer drove nothing. But **the bounded runtime adds little on failure
classification today**, and a release note claiming otherwise would be wrong.

**No reviewed ground truth exists.** Verification status is `UNKNOWN` for all 19, so no
accuracy figure is computed and none is claimed. Zero shadow disagreements is therefore
weak information, not evidence of correctness.

## 7. Calibration

**NOT PROVEN.** No calibration profile was created from this run. 19 decisions is a small
dataset, none of them have reviewed labels, and the largest family showed no
discrimination at all - a profile fitted on it would measure nothing real.

Stable does not require a profile. Requiring one here would be reading a threshold as if
it were evidence.

## 8. Defects found in this pass

| Defect | Severity | Status |
|---|---|---|
| Resolver was first-match-wins; a stale root copy could shadow a moved document | HIGH | fixed |
| Resolver had no traversal or absolute-path guard | HIGH | fixed |
| Resolver returned the bare name on zero matches, so a caller's `open` raised `FileNotFoundError` from an unrelated site | MEDIUM | fixed |
| Identity wording implied three globally-equivalent names | MEDIUM | clarified |
| `RELEASING.md` misdescribed who may publish | MEDIUM | corrected |
| A benchmark case asserted the public surface against a module that never had it | LOW | fixed earlier, now in the release subset |

The stable-prep audit found nothing in the Decision Runtime itself: no authority leak, no
cache contamination, no hang, no profile mismatch, no mislabelled confidence, and shadow
mode could not influence execution on any of the 19 real decisions.

## 9. Test counts

| Suite | Count |
|---|---|
| `test-decision-runtime.py` | **510/510** |
| `test-decision-runtime-mutations.py` | **38/38** mutations caught |
| `test-engine-core.py` | **578/578** |
| `test-decision-mutations.py` | **9/9** mutations caught |
| release subset | **79/79**, 0 fail, 0 error |
| `test-release.py` | **97/97** |
| `test-distribution.py` | **55/55** |
| repository contract | PASS |
| release gate | **GREEN**, 12/12 |

Six new mutations, all for the resolver: first-match, ignore-a-missing-document, accept
traversal, accept absolute paths, skip the containment check, search the whole
repository. The containment-check mutation needed a *traversing root* to be observable,
because a traversing name is already refused by the earlier name check - without that, the
mutant survived and proved nothing.

## 10. Stable source commit and artifacts

```
70e203c91ac56d3611eac3aed22491b1c7bac41b
```

`HEAD` = descriptor `source_commit` = `v2.1.0` tag target, all identical.

```
6217ea1b85fa17f698331faa556af65f13f520f920bf5f9f6d441e045321f892  ariadne-runtime-2.1.0.zip
23ac0a1a38df072754d1e87818b2e30fb5bca9db7fb54670ced51640d736471e  ariadne-2.1.0-py3-none-any.whl
774b6bad4eb123578ee8be63404967ec5c7ea94e46b891a46cbf287f8ec69b90  ariadne-release.json
6d4ba7c53a1a1bd69246bc65b4f1da58feffc06107193c4f0faf3bade9f81b1f  ariadne-2.1.0-release-notes.md
```

The gate refused the first attempt because `dist/` still held the RC artifacts and the
descriptor said `2.1.0rc1`. That is the invariant working: RC artifacts are not stable
artifacts.

## 11. Tag and release

```
v2.1.0  ->  70e203c91ac56d3611eac3aed22491b1c7bac41b
https://github.com/tanishkfr/ariadne/releases/tag/v2.1.0
prerelease: false   draft: false   latest: true
```

`v2.1.0rc1` remains published as a pre-release. Stable coexists with it.

## 12. Public artifact smoke

The **published** wheel was downloaded, not the local one. SHA-256 matched the release
record exactly for the wheel, the runtime bundle and the descriptor.

Clean-installed into a fresh environment outside the checkout:

| Check | Result |
|---|---|
| `python -m ariadne --version` | `Ariadne 2.1.0` |
| install runtime bundle | installed |
| doctor, no runtime | healthy; runtime *not installed (optional)* |
| doctor, runtime present | healthy; smoke 0.08ms; calibration inactive |
| bounded decision | `IMPLEMENTATION_FAILURE` (`PROVIDER_PROBABILITY`) |
| no-profile path | answered, no threshold invented |
| authority | `none`, `acted_on: false` |
| shadow | effect `none`, authority `none` |
| uninstall | clean |

## 13. Remaining limitations

1. **No calibration profile ships.** A fresh install is ungated by design.
2. **The reference engine is rule-derived, not trained**, and on failure classification it
   does not discriminate real build output today.
3. **No automatic training**, and no guarantee any decision family is calibrated.
4. **Local performance is hardware-dependent.** The 0.48 ms sidecar figure is one
   machine, one question; process startup dominates a cold sidecar.
5. **`SHA256SUMS.txt` lists `ariadne-2.1.0-release-notes.md`, which is published as the
   release body rather than as an attached asset.** The three attached artifacts all
   verify; the fourth is verifiable only from the release body. Minor, and recorded
   rather than papered over.
6. **Not published to PyPI.** The `ariadne` name belongs to an unrelated GraphQL server,
   so GitHub Releases remains the distribution mechanism.
7. **The real-world run had no reviewed ground truth**, so it demonstrates the pipeline
   and not its accuracy.

Nothing here is a reason to withhold stable, and the seventh is the one to keep in mind
when adopting: the architecture is proven, the accuracy of the shipped engine is not.
