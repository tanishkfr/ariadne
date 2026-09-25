# AR-205 — 06 — Release API: Python and CLI

## Public Python API

`ariadne_engine.public` is the deliberate v2 surface. It names three stability
classes and exports one embedding entry point:

```python
from ariadne_engine import public

client = public.connect("/path/to/runtime")   # or omit to reuse a loaded runtime
result = client.start_run(project="/path/to/project", request="describe the work")
print(result.exit_code, result.message)
```

- **`STABLE_V2`** (37 names): `Result`, `format_result`, the lifecycle
  operations (`start_run`, `status`, `approve_gate`, `prepare_next`,
  `record_result`, `ingest_return`, `validate_worker`, `prepare_review`,
  `ingest_review`, `record_acceptance`), recovery, events, capability and
  verification inspection, the Decision Plane inspection operations, economics,
  the migration operations, and the embedding entry point.
- **`PROVISIONAL`** (54 names): the adaptive-execution, design-intelligence,
  provenance, capability-probe, artifact and orchestration helpers. Real and
  tested, expected to evolve within v2.
- **`INTERNAL`**: `bind`, `runtime`, and every name not listed above.

Rules enforced by the release gate (`release.public_surface_problems`):

- every exported `api.__all__` name carries exactly one class;
- a class never names a non-exported operation;
- an accidental new export fails the gate until it is deliberately classified;
- importing the public surface loads no Boreal, Tauri, React, OpenCode, paid
  provider, network client or optional dependency.

## CLI

Two command lines ship:

**Launcher (`python -m ariadne`)** — install and lifecycle: `install`, `doctor`,
`update`, `rollback`, `uninstall`, `enable-claude`, `disable-claude`,
`codex-baseline`, `paths`, `--version`.

**Runtime (`python scripts/ariadne.py`, installed as the managed runtime)** — the
project workflow. v1 command names and exit codes are unchanged. AR-205 adds:

| Command | Purpose |
|---|---|
| `ariadne migrate --dry-run` | inventory and plan; writes nothing (default) |
| `ariadne migrate --apply` | backup, additive migration, evidence record |
| `ariadne migrate --rollback` | restore preserved bytes while honest |
| `ariadne --version` | version plus engine contract line |

Help text is grouped by the workflow; internal helper commands remain available
for operators but are not advertised in the README.

## Configuration

Configuration precedence, from lowest to highest:

1. engine defaults (`efficiency.DEFAULT_FLAGS`, stage tables, policy constants);
2. the run state's recorded `efficiency` block, which is explicit once written;
3. an explicit command-line or API argument for this call.

Rules:

- an unknown efficiency setting name is refused (`set_efficiency_config`);
- an invalid value for a known setting is refused by `config_problems`;
- the resolved configuration carries a digest, so a report can state which
  profile produced it;
- secrets are never persisted in run state or evidence: worker-sensitive paths
  are fingerprinted by metadata rather than read, and rendered requests redact
  detected secrets.

## Error experience

Expected failures are printed as `STOPPED: <reason>` on stdout and exit `1` (or
`2` when the run pauses for a human). Each message says what was refused and what
remains safe. Common cases, all benchmark- or suite-tested:

| Situation | Message shape | State |
|---|---|---|
| pre-engine run state | names the contract and asks for `--migrate` | unchanged |
| malformed or unsupported state | `Run state is malformed: …` / `Run state schema is unsupported` | unchanged |
| migration with unsupported data | names each blocking object | unchanged |
| rollback after v2 work | says what would be discarded and where the backup is | unchanged |
| missing provider or capability | capability state reports unavailability | unchanged |
| invalid or stale approval | names the gate, target or revision mismatch | unchanged |
| failed validation | records the failing command and the classified failure | recorded, not hidden |
| incompatible consumer protocol | names the supported range | unchanged |

Unexpected exceptions still produce a traceback for debugging; expected
contract failures never do.

## Contracts

- Exit codes are unchanged: `0` success, `1` stopped/refused, `2` paused.
- Expected failures print `STOPPED: <reason>` and never a stack trace; the
  traceback path stays available for unexpected exceptions.
- The API and the CLI call the same engine functions, so API users cannot get
  weaker enforcement than operators.
- Version consistency is checked by the release gate across `VERSION`, the
  launcher metadata, the runtime, the release manifest, the install documents
  and the installation example.
