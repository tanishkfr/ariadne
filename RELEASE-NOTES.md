# Ariadne 2.1.0rc1

Ariadne 2.1.0rc1 adds the **native Decision Runtime**: an on-device bounded inference
engine that answers Ariadne's own Decision Plane questions, isolated in a sidecar
process. It is a feature drop on top of 2.0, and every 2.0 behaviour is preserved.

The 2.0 notes follow below.

Install from the GitHub release artifacts. PyPI publication stays deferred
because the `ariadne` distribution name belongs to an unrelated GraphQL server;
this release is delivered as an immutable wheel and runtime bundle.

## The Decision Runtime, in one paragraph

When a requirement needs a bounded judgement, Ariadne now has somewhere local to ask.
The runtime answers one projected state and many independent questions in a single
inference, over closed answer spaces the question declared, and it refuses rather than
guesses. It observes before it influences: the authoritative answer is decided, judged
and recorded first, and the runtime's prediction is stored beside it as evidence that
provably could not have changed it. A probability is only labelled calibrated when a
measured profile matches runtime kind, implementation, model revision, decision
definition, question version and question schema exactly. Promotion to an
authoritative role is scoped, ordered and reversible. The default posture is shadow, and
nothing is promoted by default.

## What is genuinely new in 2.1

- **A native bounded engine.** A reference implementation, pure standard library, with
  weights derived from Ariadne's own declared decision vocabularies. No model download,
  no network, no training, no third-party runtime component and no ML dependency. It is
  installed as a data directory, so a runtime can be replaced without replacing a
  program.
- **A sidecar isolation boundary.** The engine runs in a separate process speaking a
  four-method JSON-lines protocol, so a wedged or crashing runtime cannot take an Ariadne
  process with it. Its stderr is drained continuously, its timeouts are real deadlines,
  and closing a session is final.
- **A real abstention.** Four structured reasons - `NO_LOCAL_MODEL`,
  `BELOW_MIN_CONFIDENCE`, `UNSUPPORTED_PRIMITIVE`, `ANSWER_SPACE_MISMATCH` - and **no
  default confidence threshold anywhere**. Thresholds are the caller's or the policy's
  decision to state, and the engine has no opinion unless asked.
- **Calibration as a measured claim.** `PROVEN` requires a dataset at or above the
  floor; a profile speaks only for the risk classes it declares; a moving alias satisfies
  nothing; and the runtime cannot declare its own probabilities calibrated.
- **Shadow mode with a check, not a promise.** Shadow records are structurally incapable
  of carrying an execution effect, an isolation check surfaces a record that claims
  otherwise, and ground truth must name its source before it is stored.
- **Scoped, ordered, reversible adoption.** `UNTESTED -> SHADOW -> EVALUATED -> ELIGIBLE
  -> ACTIVE`, with every transition requiring a reason, an evaluation identity and a
  calibration profile, and with scope (risk class, reversibility, verification
  availability, languages) checked per call rather than trusted from a record.
- **Identity-bound metrics.** Evaluation metrics are only compared across runs whose
  experiment identity matches exactly. Otherwise the gate refuses rather than printing a
  delta across two different experiments.

## What 2.1 does not do

Stated plainly, because a release note that oversells is worse than none.

- The reference engine is **rule-derived, not trained**. It is strong on enumerated
  structure and weak on prose, and it says so in its own docstrings.
- The installed runtime's probabilities are **uncalibrated**. No profile ships with it.
- **Nothing is promoted to `ACTIVE` by default.** Shadow is the shipped posture.
- `MultiSelectDecision` is **deliberately unsupported** and takes the normal fallback
  and escalation path.
- The threshold abstention machinery exists and is tested, but `batch.evaluate` builds a
  request with no policy, so `BELOW_MIN_CONFIDENCE` does not fire on the default path
  yet. That is a deliberate open item, not a working feature.
- `python -m ariadne doctor` does **not** check the Decision Runtime. The engine
  controller's `ariadne decision-runtime --action doctor` does.

## Verification

    scripts/test-decision-runtime.py            366 functional checks
    scripts/test-decision-runtime-mutations.py  15/15 protections load-bearing
    scripts/test-engine-core.py                 578/578, unchanged from 2.0
    scripts/test-decision-mutations.py          9/9, unchanged from 2.0

All four suites now run from `scripts/release-check.py`. Through 2.0 the gate could be
declared green on a tree whose engine had never been executed.

An adversarial review against twelve attack classes found two critical and seven high
defects, all of which passed the functional suite: a timeout that was not a deadline, an
undrained stderr pipe, a profile retirement that never reached the state, a
self-declared confidence kind forwarded verbatim, a latched model revision, an
evaluation gate that passed when a candidate stopped reporting a metric, a comparison of
reports that carried no identity, a calibration measured on LOW risk relabelling a
PROTECTED decision, an unguarded manifest path, and a second moving-alias list. All are
fixed, and each has a check that fails against the pre-fix behaviour.

## Migration

Additive. A 2.0 caller with no runtime configured produces a byte-identical result plus
one extra inert key, `shadow`, which always reports `execution_effect: "none"`. There is
no new required argument anywhere, no migration step, and no `--decision-provider` flag
to configure, because there is no provider choice to make: Ariadne finds a Decision
Runtime or it does not.

Full documentation: [docs/v2/2.1/](docs/v2/2.1/README.md).

---

# Ariadne 2.0.0

Ariadne 2.0.0 is the first stable release of the v2 execution engine. It turns
the runtime into an executable orchestration core with recorded evidence, and it
adds bounded Decision Intelligence as a normal way to answer closed questions
without calling a generative model.

Install from the GitHub release artifacts. PyPI publication stays deferred
because the `ariadne` distribution name belongs to an unrelated GraphQL server;
this release is delivered as an immutable wheel and runtime bundle.

## Highlights

### Adaptive execution

A task is characterised before work begins, and context, routing and recovery
are traced decisions with explicit policies and recorded inputs. Each stage
transports only the sources it declared, and the decision layer may omit a
source only when the transport marked it removable.

### Decision Intelligence

The Decision Plane classifies every unresolved requirement as deterministic,
bounded, generative, human or unresolved. Deterministic facts are answered by
code first. Bounded questions use a declared option set and a minimal state
projection, are batched with independent siblings, and are cached only against a
concrete provider model version. Ambiguity escalates instead of resolving into a
confident guess, and a protected action is refused under every confidence.

### Verification hardening

Execution identity, provider observation and measured usage are separate
records. A verification binds its revision and its evidence level, stale
evidence cannot close a gate, and capability evidence advances only from
`DECLARED` through `OBSERVED` and `EXERCISED` to `VERIFIED`. Review independence
is enforced at the engine level, so an implementer cannot certify their own work.

### Design Intelligence

Design provenance is recorded rather than described: requirements, reference
findings, component candidates, an approved direction, rendered evidence with
capture parameters, an independent critique and bounded refinements. Source
inspection cannot close a rendered-quality requirement.

### Context economics

Task-level usage, context attribution and verified-completion cost are derived
from records, and unknown values stay unknown. Byte or turn reductions are never
presented as a quality or cost saving, because no live provider comparison was
executed.

### Standalone API

A versioned, provider-neutral consumer contract and a stability-classified
Python surface let another application drive the engine. The contract is
verified against Ariadne's own side with deterministic fixtures; it is
contract-verified, not a live editor integration.

### Migration and release safety

`ariadne migrate --dry-run` inventories a v1-era run and states its plan without
writing. `ariadne migrate --apply` is additive, preserves the original bytes and
creates no approval, review, validation or capability record. The release gate
refuses to call a build ready while a version surface, an artifact hash, a
migration rule or an experimental default disagrees with what the release claims.

## Compatibility and breaking notes

- A run state written before the engine contract marker is refused until it is
  migrated explicitly. Read-only inspection of project documents and legacy
  ledgers continues to work.
- Fresh installs register the managed skill under `~/.agents/skills/ariadne`;
  an earlier Ariadne-managed skill under a legacy Codex path is reused in place.
- The Python distribution and import name is still `ariadne`, shared on paper
  with the unrelated GraphQL project. The two cannot share one Python
  environment.
- No new environment variable is required, and the declared exit codes are
  unchanged: `0` success, `1` stopped or refused, `2` paused or needs-human.

## Migration

The migration path is explicit and reversible where it can be honest. It is
described in full in `MIGRATING-v1-to-v2.md`:

```bash
python -m ariadne migrate --dry-run --project <project>
python -m ariadne migrate --apply --project <project>
python -m ariadne migrate --rollback --project <project>
```

Rollback restores the preserved bytes while the migrated state is unchanged, and
refuses after further v2 work instead of discarding records.

## Experimental features

Seven behavior-sensitive settings from the harness-economics work remain
experimental and off (or at their legacy default) until a measured
quality comparison exists: `prompt_profile`, `tool_loading`, `compaction`,
`context_reduction`, `history_format`, `routing_economics` and `packet_order`.
The evidence-preserving `output_externalization` default is unchanged. The
release gate fails if any of these defaults moves. Details are in
`docs/v2/AR-205/09-EXPERIMENTAL-FEATURES.md`.

## Known limitations

- No live decision provider or model-quality comparison was executed, so no
  calibration, threshold or provider-quality claim is made. Structural counters
  are not money.
- The Jev-shaped decision-provider boundary is present but unexercised. It is an
  example of a possible provider, not a dependency or an identity.
- Boreal compatibility was inspected read-only and is contract-verified only;
  no live Boreal runtime verification was performed.
- Ariadne does not sandbox the operating system, does not cryptographically
  attest local run-state files, and cannot prove an observation a provider never
  reported.
- Prompt injection from external text remains possible inside a model's own
  authority; the engine limits the blast radius rather than eliminating it.
- Release artifacts are authenticated by digest and by an embedded manifest, not
  by a maintainer signing key.
- Migration rollback is unavailable once a migrated run contains v2-only work;
  the preserved pre-migration bytes remain for manual recovery.
- Artifact signing is not implemented. Clean-install verification was performed
  on Windows; macOS and Linux share the same Python entry point but were not
  executed in this release run.

## Platforms and installation

Install with `python -m pip install --user` and the release wheel URL, then run
`python -m ariadne doctor`. The launcher is a single dependency-free Python
entry point used on Windows, macOS and Linux, and the installed runtime stays
offline. The stage packets are written so that a first-time-user can follow them,
and the platform names, comprehension guidance and Codex skill location are
documented in `INSTALL.md` and `QUICKSTART.md`.

## Evidence limits

This release was verified with deterministic offline tests: the repository
contract, engine-core checks, the full benchmark, the release suite, a clean
wheel installation, and the migration and decision-mutation checks. It makes no
claim about model output quality, provider equivalence, sandboxing or live
integration with any consumer application. See `TRUST.md` for the exact
boundaries.
