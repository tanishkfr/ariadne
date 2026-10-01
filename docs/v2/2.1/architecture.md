# Architecture

## The shape

```
                     ariadne_engine.decisions.runtime.session.DecisionRuntime
                                          |
        +---------------------------------+---------------------------------+
        |                                 |                                 |
   manifest.py                       transport.py                      sidecar.py
   what is installed,               InProcessTransport                four methods,
   is it the reviewed one           SubprocessTransport                one JSON line
   |                                 UnavailableTransport               per request
   |                                        |                              |
   |                          +-------------+--------------+               |
   |                          |                            |               |
   |                   reference.py                  (a future            |
   |                   the reference engine          checkpoint-           |
   |                   + seeds.py                    backed engine         |
   |                   rule-derived weights         installed the         |
   |                                             same way)              |
   +-------------------------------+---------------------------------------+
                                   |
   provider.py  selection.py  observe.py  shadow.py  profiles.py  promotion.py
   evaluation.py  export.py  schema.py  shortlist.py  integrity.py
   the integration into the Decision Plane, and the machinery that makes
   using one safe: shadow, calibration, promotion, evaluation, export
```

Two halves. The first half answers a question; the second half is what makes it
safe to answer a question at all.

## Components

| Module | Responsibility |
|---|---|
| `session.py` | `DecisionRuntime`: the narrow user-facing API, capability state, and installation discovery. |
| `transport.py` | The boundary. `InProcessTransport`, `SubprocessTransport`, `UnavailableTransport`, and the wire schema constant. |
| `sidecar.py` | The executable. Reads one JSON document per line, answers one per line. Deliberately not imported by the package. |
| `reference.py` | The reference bounded engine: a multinomial naive-Bayes log-odds scorer. |
| `seeds.py` | The first weight set, derived from Ariadne's own deterministic decision tables. |
| `manifest.py` | What an installation is (`runtime-manifest.json`), and byte-level verification against a reviewed digest record. |
| `integrity.py` | Requested versus observed versus reviewed; the only path to `PASS`. |
| `provider.py` | `LocalBoundedProvider`: the adapter into the existing Decision Plane. |
| `selection.py` | How Ariadne chooses its own bounded implementation. No picker. |
| `observe.py` | Shadow observation beside an already-made decision. |
| `shadow.py` | The shadow record, the agreement states, the comparison, the isolation check. |
| `profiles.py` | `CalibrationProfile` and `profile_for`, the only route to `CALIBRATED_PROBABILITY`. |
| `promotion.py` | Adoption slices: the lifecycle, the scope, the transitions. |
| `evaluation.py` | Identity-bound evaluation and the comparability gate. |
| `export.py` | The labelled-dataset export, which stops short of training. |
| `schema.py` | A safe subset of JSON Schema compiled into Ariadne primitives. |
| `shortlist.py` | Deterministic narrowing before a large candidate set becomes a question. |

`sidecar.py` is the one module the package `__init__` does not import. Importing
an entry point would put `argparse` and a `main` on the import path of every
Ariadne process; the transport launches it by file path instead.

## The sidecar protocol

Four methods. That is the entire wire contract:

| Method | Request payload | Answer |
|---|---|---|
| `status` | `{}` | Identity and capability facts: availability, runtime version, implementation and its revision, model and its revision, supported primitives, device, whether the engine is warm, the confidence kinds it offers, whether it claims its own calibration, and a weight-book summary. |
| `decide` | `state`, `questions`, optional `min_confidence` | One state, many questions, as one bounded inference. |
| `decide_batch` | `states`, `questions`, optional `min_confidence` | Many states, many questions, still one call. |
| `warm` | `{}` | Marks the engine ready ahead of the first real question. |

The surface is narrow on purpose. The value of the isolation comes from the
boundary being small enough that swapping the engine cannot change Ariadne's
behaviour; a runtime that needed twenty methods would be an authority, not a
classifier.

### The wire schema

Every request carries and every reply echoes the same version string:

```
ariadne-decision-runtime-wire/1
```

`WIRE_SCHEMA` in `transport.py`. The sidecar refuses a request whose `schema`
field is anything else; the transport closes the child and raises if a reply's
schema does not match. Bumping the engine without bumping this string is how a
stale process silently answers with another engine's semantics.

### The framing

One JSON object per line on standard input, one JSON object per line on standard
output. Nothing else is ever written to standard output - diagnostics go to
standard error so they cannot corrupt the stream. There is no length prefix, no
framing trick and no batch-of-batches envelope: the sidecar reads a line, answers
a line, flushes.

Request shape:

```
{"schema": "ariadne-decision-runtime-wire/1", "method": "decide_batch", "payload": {...}}
```

Reply shape is either `{"schema": ..., "result": {...}}` or
`{"schema": ..., "error": "..."}`.

**Failure is reported, never guessed.** An exception inside a request becomes an
`error` reply carrying `TypeName: message`, which the transport turns into
`RuntimeTransportError`. The sidecar does not exit on a bad request: one malformed
projection must not take the engine down for the rest of the run. A failure to
load the engine at all is the exception - it writes
`decision runtime failed to load: ...` to standard error and exits `2`.

## Transports

Three implementations of one four-method protocol
(`RuntimeTransport`: `describe()`, `available()`, `call()`, `close()`).

### `SubprocessTransport` - the shipping route

Launches the sidecar by file path and exchanges newline-delimited JSON over its
standard streams. Four properties it has to hold, because they are the difference
between a sidecar and a liability:

- **Isolation.** Ariadne never imports the engine. A segfault in a native
  operator takes down the sidecar, which Ariadne records as `DECISION_FAILED` and
  routes to the normal fallback.
- **Bounded cost.** Every call has a deadline. `DEFAULT_CALL_TIMEOUT_SECONDS` is
  30 for a call; `DEFAULT_STARTUP_TIMEOUT_SECONDS` is 120 for the first `status`,
  which is generous because checkpoint loading is genuinely slow the first time
  and bounded because an unbounded wait would hang the whole task. The child is
  terminated on every timeout, because `readline` on a pipe has no deadline of its
  own and a wedged engine must not leak one blocked reader per call forever. On
  Windows the child is created with `CREATE_NO_WINDOW` in its own group; on
  POSIX with `start_new_session=True`, so `close()` can `killpg` the whole tree
  rather than orphaning a grandchild holding the pipes open.
- **No wedging on stderr.** A child that fills its stderr pipe stops reading stdin
  and wedges every caller. A reader thread (`_StderrBuffer`) starts before the
  first handshake and drains continuously; the timeout path reads that in-memory
  buffer for the failure detail and never touches the pipe, because a blocking
  read of the pipe returns only at EOF - which for a child that is still alive is
  never. Killing precedes closing the pipes, and `process.stderr` is left to the
  reader thread rather than closed underneath it.
- **No shell.** The command is a list, never a string. A path containing spaces -
  which on Windows is most paths - works, and nothing in a manifest or an
  environment variable is ever interpreted by a shell.

The argv is `[sys.executable, "<...>/runtime/sidecar.py", "--root", "<installation>"]`.
The *code* ships in the wheel; the *data* (manifest and weights) lives in the
installation directory. That split is why a runtime can be updated by replacing a
data directory without replacing a program.

`transport.sidecar_environment()` prepends Ariadne's own source root to `PYTHONPATH`
for the child, so the sidecar's `ariadne_engine` import resolves without requiring
Ariadne to be pip-installed into whichever interpreter happened to launch it.

### `InProcessTransport`

Wraps an engine object already living in this interpreter, serialised by a lock
so two calls cannot interleave inside one engine and make batch results
order-dependent. An in-process failure is re-raised as `RuntimeTransportError`,
so it is indistinguishable from a subprocess failure to the caller. Used by the
deterministic fixture and by the test suite; the suite asserts the two routes
produce identical answers.

### `UnavailableTransport`

The honest default, and a complete implementation. `describe()` returns an
unavailable fact set, `available()` returns `(False, reason)`, and `call()` always
raises. Nothing installed, nothing to load, and the caller falls back.

## Discovery

`DecisionRuntime.discover()` never raises for a missing or broken runtime. "Not
installed" and "installed but will not start" are normal states the caller routes
around, and the reason is preserved.

Search order, first match wins:

1. an explicitly passed `root=` (tests, advanced configuration);
2. `ARIADNE_DECISION_RUNTIME` in the environment;
3. `<data home>/decision-runtime/current`;
4. `<data home>/decision-runtime/<ariadne version>`.

`user_data_home()` mirrors the launcher's own convention exactly, including the
`ARIADNE_DATA_HOME` override, so the Decision Runtime installs and uninstalls
with the rest of the product instead of inventing a second place for itself:

| Platform | Data home |
|---|---|
| Windows | `%LOCALAPPDATA%\Ariadne` |
| macOS | `~/Library/Application Support/Ariadne` |
| Linux | `$XDG_DATA_HOME/ariadne`, otherwise `~/.local/share/ariadne` |

A directory only counts as an installation if it contains a `runtime-manifest.json`
that parses and validates. `find_installation()` records *every* place it looked
in `searched`, including the one that matched: "found in the first place" and
"found in the fourth" are different facts about a machine, and a diagnostic that
cannot tell them apart is hiding a configuration problem.

## The process lifecycle

**Start is lazy.** No process exists until something asks. `discover()` builds the
`SubprocessTransport` and calls `status()` once, which starts the child and
performs the handshake; a failure at that point returns an *unavailable runtime
carrying the reason*, not an exception. The transport's own `available()` reason
is deliberately not reused there: it reports that the sidecar is installed, which
is true and is the opposite of the fact the user needs.

**Calls are serialised.** One call at a time, per transport, behind a lock.

**A dead child is respawned transparently, and the identity is re-read.** If the
process exits between calls, the next call starts a new one. That replacement may
be a different build, so `LocalBoundedProvider.model_version` asks the runtime
what revision it reports *now* rather than latching the value from startup - a
latched revision would stamp an answer computed by the new build with the old
one, and serve the old revision's cached answers to a new engine.

**`warm` refreshes cached status.** Without that, `status` would keep reporting
the `cold` it saw at process start, and a user who just paid the load cost would
be told the runtime is still not ready.

**Status vocabulary.** `AVAILABLE`, `AVAILABLE_CPU`, `AVAILABLE_GPU`, `WARM`,
`COLD`, `WARMING`, `UNAVAILABLE`, `UNAVAILABLE_RESOURCE`,
`UNAVAILABLE_LICENSE`. The state is derived from availability, device and warm
flag: unavailable reasons mentioning resource, memory or device become
`UNAVAILABLE_RESOURCE`; a reason mentioning a licence becomes
`UNAVAILABLE_LICENSE`; anything else is plain `UNAVAILABLE`. A warm engine is
`WARM`; a cold CPU engine is `COLD` with detail `available (cold)`; a cold GPU
engine is `COLD` with detail `warming`. Six of the nine are produced today; see
[Operations](operations.md).

**Shutdown is final and safe to repeat.** `close()` sets a disposed flag and a
closed transport refuses to start again - `RuntimeTransportError`, not a silent
respawn, because a transport that resurrects itself after being closed turns a
deliberate shutdown back into a live process. `DecisionRuntime.shutdown()` then
swallows that error: shutdown must never raise. The session is also a context
manager.

## What crosses the boundary

Only the four methods, and every crossing value is JSON. A projected state
crosses; projected state is by construction already the smallest defensible slice
of the run, built by `ariadne_engine.decisions.projections`. Question records
cross, carrying the contract, the primitive, the declared answer space and the
definition version. Everything else - the run state, the evidence, the
repository, credentials - does not cross.

## Events

The runtime has its own lifecycle vocabulary, declared in
`contracts.DECISION_RUNTIME_EVENT_TYPES`:

```
decision_runtime_requested      decision_runtime_abstained
decision_runtime_started        decision_runtime_failed
decision_runtime_completed      decision_runtime_cache_hit
decision_runtime_shadow_recorded
decision_runtime_promoted       decision_runtime_suspended
```

These are ordinary `ariadne_engine.events` entries. Ariadne has one event system
and the Decision Runtime does not get a second one. Today three of the nine are
emitted - `decision_runtime_completed` by the evaluation action,
`decision_runtime_promoted` and `decision_runtime_suspended` by the promotion
action. The remaining six are declared vocabulary with no emitter yet; nothing
depends on them, and no claim should be made about them.
