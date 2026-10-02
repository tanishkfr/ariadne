# Operations

A normal user never runs any of these commands. Ariadne finds the Decision Runtime
by itself, uses it where policy allows, and falls back safely when it cannot. This
document is for the three cases where somebody has to answer a question the
product deliberately does not answer for you: is it installed, is it the one we
reviewed, what has it actually been measured at, and does an adoption slice cover
this decision.

The CLI entry point is the engine controller, `scripts/ariadne.py`. It is not the
launcher: `python -m ariadne doctor` checks installation health and does **not**
report the Decision Runtime.

## The command

```
python scripts/ariadne.py decision-runtime
    [--run-root RUN_ROOT] [--project PROJECT]
    [--action {status,doctor,install,eval,promote}]
    [--root ROOT] [--definition DEFINITION] [--input INPUT]
    [--baseline BASELINE] [--slice-id SLICE_ID] [--to TO]
    [--reason REASON] [--evaluation-id EVALUATION_ID] [--json]
```

`--action` defaults to `status`. Every action accepts `--json` and exits
non-zero when the state it reports is a refusal, so all five are scriptable.

Two structural notes from the source, because they are deliberate. The command
declares `--run-root` and `--project` directly rather than through the shared run
selector, because `status` and `install` are facts about the machine and forcing
them to name a run would require creating a run just to ask whether a runtime
exists. And `status` and `install` return **before** the run state is resolved,
while `doctor`, `eval` and `promote` resolve it first - they are evidence about a
run, not about a machine.

## status

```bash
python scripts/ariadne.py decision-runtime --action status
```

On an installed reference runtime this prints:

```
Decision Runtime: available (cold)
  primitives    : BinaryDecision, ChoiceDecision, ScaleDecision
  unsupported   : MultiSelectDecision (these use the normal fallback)
  runtime       : 1.0.0 / ariadne-reference-bounded @ ar-206-reference-1
  model revision: ar-206-reference-1
  device        : cpu
  digests pinned: no (bytes are undescribed, not verified)
```

and exits `0`. With nothing installed it prints `Decision Runtime: unavailable`,
lists every Ariadne primitive as unsupported, adds
`Continuing through the safe fallback path.`, and exits `2`.

The product vocabulary leads every view. The implementation identity follows it,
because provenance that cannot name its implementation is not evidence - but it is
not what a user has to understand.

`--root <dir>` inspects a specific installation directory instead of searching.
`--json` returns the full status record (twenty fields, including
`calibration_self_granted`, `digest_pinned`, `transport`, `runtime_kind`, `root`
and the `note` that reads "bounded local inference; never an authorization and
never verification") with the same exit code.

## install

```bash
python scripts/ariadne.py decision-runtime --action install
```

Writes `weights.json` and `runtime-manifest.json` into
`<data home>/decision-runtime/current`. No download, no network, no dependency,
no credential:

```
Decision Runtime installed.
  location      : <root>
  implementation: ariadne-reference-bounded (pure standard library, no download)
  families      : 4 seeded question families, 73 rule examples
  note          : probabilities from this engine are uncalibrated by construction
```

Four families and 73 rule-derived examples is the entire shipped weight book:
failure classification (28 examples, 7 classes), route family (16, 6), evidence
relevance (16, 5), review escalation (13, 4). The installation is under 4 MB -
in practice about 96 KB - and the whole install step is writing two JSON files.

`--root <dir>` installs elsewhere. This is how you keep two installations side by
side, or how a test drives the real discovery path.

## doctor

```bash
python scripts/ariadne.py decision-runtime --action doctor \
    --project <project> --run-root <run-root>
```

One read-only view of the recorded evidence: capability (from a real discovered
session), shadow record counts and the agreement breakdown, accuracy **or the
words `accuracy : unknown (no recorded ground truth)`**, adoption slice counts
with the active definitions, calibration profile and `PROVEN` counts, and every
structural and influence problem found in the shadow collection. It ends with the
line "a prediction is not verification, and nothing here authorises anything".

It resolves a run, so it needs a location. It writes nothing.

### The normal `ariadne doctor` checks it too

```bash
ariadne doctor
```

```text
[OK] Decision Runtime: healthy (1.0.0)
[OK] Decision Runtime manifest: readable; no digests are pinned, so its integrity is undescribed
[OK] Decision Runtime model: ariadne-reference-bounded ar-206-reference-1
[OK] Device: cpu
[OK] Decision Runtime smoke: answered doctor-smoke in 0.07ms
[OK] Decision Runtime calibration: 0 proven profile(s), 0 decision family(ies),
    0 active threshold(s); confidence-gated abstention is inactive
```

On a machine with nothing installed, which is the shipped default:

```text
[OK] Decision Runtime: not installed (optional)
[OK] Decision Runtime calibration: no proven profile; confidence-gated abstention is
    inactive (the runtime still answers bounded questions)
```

This is an adapter, not a second health checker: everything runtime-specific is asked of
the runtime's own code, through the same `sidecar.build_engine` the sidecar itself uses.
It runs **in-process** and takes about a tenth of a millisecond, because spawning the
sidecar on every `doctor` invocation cost about a second and made an unrelated product
check fail under load. Process startup is verified where it belongs - the transport
suites and the wheel-install gate - and the output says so rather than implying it was
checked.

Three distinctions are load-bearing.

**An absent runtime is not a fault.** Ariadne answers bounded questions without it, so it
never turns the doctor red. The optional runtime is optional.

**A working runtime is not a calibrated one.** Calibration is its own line, counting
proven profiles, decision families and active thresholds. A healthy runtime with zero
profiles reads as *healthy and ungated*, which is the truth on a fresh install. The
doctor never says "calibrated" because a runtime started.

**A readable manifest is not a verified one.** The seed installer ships no pinned
digests, and the doctor says exactly that: *readable; no digests are pinned, so its
integrity is undescribed*. Hashing the bytes you just found describes the installation;
it does not verify it. When digests *are* pinned, a mismatch is reported by filename.

## eval

```bash
python scripts/ariadne.py decision-runtime --action eval \
    --input cases.json --definition failure-classification --json \
    --project <project> --run-root <run-root>
```

`--input` takes a JSON file that is either a bare list of cases or an object:

```json
{
  "records": [
    {"case_id": "c1", "expected": "IMPLEMENTATION_FAILURE",
     "projection": {"entries": {"failure": "Traceback: TypeError in render"}}}
  ],
  "rows": [
    {"case_id": "c1", "answer": "IMPLEMENTATION_FAILURE", "confidence": 0.91,
     "distribution": {"IMPLEMENTATION_FAILURE": 0.91, "TIMEOUT": 0.09},
     "latency_ms": 0.4}
  ],
  "questions": [ ... ],
  "decision_definition": "failure-classification"
}
```

`records` are the cases; `rows` are the runtime's answers for them, matched by
`case_id`; `questions` bind the schema and definition digests. The runtime
version, implementation revision and model revision are read from the runtime that
actually loaded, not typed in - see
[Evaluation and comparability](evaluation-and-comparability.md).

It prints the eight metrics (or `unknown` for any that cannot be measured) and
writes the run state. Add `--baseline <report.json>` to attach a comparison; when
that comparison is refused it prints `comparability  : REFUSED` with each reason
and exits `2`.

It does not run the engine over your cases. It scores the answers you give it.

## promote

```bash
python scripts/ariadne.py decision-runtime --action promote \
    --slice-id <slice> --to ACTIVE \
    --evaluation-id <evaluation> --reason "measured on the reviewed dataset" \
    --project <project> --run-root <run-root>
```

`--to` accepts any declared adoption state. `--slice-id` names an existing slice;
`--evaluation-id` and `--reason` are required in practice for `ELIGIBLE` and
`ACTIVE`, and a refused transition prints `Refused: <reason>` and exits `1` -
never a traceback. On success:

```
Adoption slice <id> is now ACTIVE.
  note: this is scoped per decision definition, question version and model revision,
        and it grants no authority of any kind.
```

Suspending is the same command with `--to SUSPENDED` and a reason. It needs no
evidence and no scope check. See
[Promotion and scopes](promotion-and-scopes.md).

There is no CLI action that opens a slice or records a calibration profile;
`decision_runtime_calibration` and `promotion.open_slice` are engine-API calls.
That is deliberate - a slice and a calibration profile are judgements with
consequences, and the CLI is not where they should be made casually.

## Environment variables

| Variable | Effect |
|---|---|
| `ARIADNE_DECISION_RUNTIME` | An explicit runtime root. First search path, ahead of anything under the data home. Advanced configuration; never required. |
| `ARIADNE_DATA_HOME` | Overrides the Ariadne data home, for the launcher and the Decision Runtime identically. Mirrors `ariadne.cli.user_data_home` exactly, so a runtime installed under an override uninstalls with the same override. |
| `PYTHONPATH` | Not read for configuration. Ariadne prepends its own source root to `PYTHONPATH` for the *child* process, so the sidecar's `ariadne_engine` import resolves without requiring Ariadne to be pip-installed into the launching interpreter. An existing value is preserved after it. |
| `LOCALAPPDATA`, `XDG_DATA_HOME`, `HOME` | Platform data-home resolution only. Windows uses `%LOCALAPPDATA%\Ariadne`; macOS uses `~/Library/Application Support/Ariadne`; Linux uses `$XDG_DATA_HOME/ariadne` or `~/.local/share/ariadne`. |

## The integrity story

Three things are deliberately kept apart:

- **requested** - what the manifest names;
- **observed** - the concrete revision and file digests actually on disk;
- **reviewed** - digests from a record a human or a trusted release signed off on.

`status` reports `digests pinned: no (bytes are undescribed, not verified)` for the
reference installation, because `default_manifest` sets `files: None` rather than
filling it in from the installation. That is honest: the reference runtime has no
reviewed digest record shipped with it, so its bytes are undescribed.

Verdicts are `PASS`, `FAIL`, `UNKNOWN`, and:

> **`UNKNOWN` is a real result.** It means no trusted digest record was supplied.
> The runtime may still load, but nothing here can claim the bytes were reviewed.

`integrity.verify_against(root, reviewed)` is the only function in the Decision
Runtime that can return `PASS`, and it needs a reviewed digest map:

```python
from pathlib import Path
from ariadne_engine.decisions.runtime import integrity, manifest

root = Path("<installation directory>")
reviewed = {
    "runtime-manifest.json": "<sha256 recorded at review time>",
    "weights.json": "<sha256 recorded at review time>",
}
print(integrity.verify_against(root, reviewed))
# {'status': 'PASS', 'checked': 2, 'source': 'reviewed digest record', ...}
```

A changed byte gives `FAIL` with the mismatched path named. A digest map that names
an absolute path or traverses with `..` raises `ContractError` before any file is
opened.

### The rule that matters

**A freshly computed digest of the bytes you just found is not verification.**
Hashing what you downloaded and comparing it to that same hash proves only that the
file did not change between the hash and the load. It says nothing about whether
the file is the reviewed one, and Ariadne will not perform it and call the result
a pass. `integrity.require_reviewed_digests(None)` returns `UNKNOWN`, not `PASS`,
and that refusal is the rule made into a function.

There is also **no signature**. Ariadne has no signing infrastructure and no key
hierarchy, so release artifacts and runtime bytes are authenticated by digest
against a reviewed record, not by a maintainer key. Inventing a verifier without
one would be theatre.

## Troubleshooting

Start with `status`. The `status` field is one of nine declared values. Six of
them are produced today:

| State | What it means | What to do |
|---|---|---|
| `UNAVAILABLE` | nothing installed, or the manifest is missing or invalid | run `--action install`, or set `ARIADNE_DECISION_RUNTIME` |
| `UNAVAILABLE_RESOURCE` | the reason mentions resource, memory or device | nothing; the safe fallback runs. A resource-limited runtime has its own status rather than a generic failure. |
| `UNAVAILABLE_LICENSE` | the reason mentions a licence | resolve the licence, or fall back |
| `COLD`, detail `available (cold)` | installed, loaded, not warmed, CPU | nothing; call `warm` if you care about the first-call state |
| `COLD`, detail `warming` | installed, not warmed, device reports `gpu` | nothing; this is the device-dependent branch |
| `WARM` | `warm()` succeeded | nothing |

`AVAILABLE`, `AVAILABLE_CPU`, `AVAILABLE_GPU` and `WARMING` are declared in
`DECISION_RUNTIME_STATUSES` for transports that distinguish more finely, and no
code path produces them today. A status parser should accept them; no diagnostic
should be surprised by them.

The `problems()` reasons, and what each means:

| Reason | Cause |
|---|---|
| "no decision runtime installation was found in ..." | nothing at any search path; the reason lists every path considered |
| "the decision runtime declares no primitives" | a malformed or stub runtime |
| "the decision runtime claims to grant its own calibration" | an engine asserting it is calibrated. A refusal by design. |
| "the decision runtime names no concrete model revision" | nothing to bind a cache entry or a slice to. The provider also refuses for this. |

Other common situations:

- **`status` exits 2 with no runtime.** Not an error. Ariadne is fully functional
  on its 2.0 safe fallback and the message says so.
- **`doctor` or `eval` refuses to run with no location.** These actions resolve a
  run. Pass `--project` and `--run-root`.
- **`eval` prints `comparability : REFUSED` and exits 2.** Correct behaviour. The
  reasons name the differing identity keys. Fix the experiment identity or accept
  that the two runs are not comparable.
- **`promote` prints `Refused:` and exits 1.** The lifecycle refused the
  transition. Read the message: it names the current state and the allowed
  targets, or the missing evaluation id.
- **A question abstains with `NO_LOCAL_MODEL`.** That question's identity digest is
  not in the weight book. It is not a failure; it is the runtime saying it has
  nothing fitted for this question. Fit a family or accept the fallback.
- **`digest_pinned` is `false`.** Expected for the reference installation. See the
  integrity story above.
- **Many `influence_problems`.** A recorded decision shares a question and
  projection digest with a shadow record but records no execution. Treat this as a
  genuine finding, not noise; `observe.require_isolated()` raises on the same
evidence.

## Running the suites

```bash
python scripts/test-decision-runtime.py
python scripts/test-decision-runtime-mutations.py
```

Both run offline, write only into a temporary directory, and assert afterwards
that they left the source tree byte-identical. The first exercises the shipping
subprocess sidecar and the in-process engine and asserts they agree; the second
removes each load-bearing guard in turn and asserts a check fails.

Both run from the release gate:

```bash
python scripts/release-check.py
```

which includes them under the *engine suites* check. A gate that does not run the
engine cannot honestly say the engine works.
