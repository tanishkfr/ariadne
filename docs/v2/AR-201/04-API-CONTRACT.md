# AR-201 — 04 API CONTRACT

The narrow programmatic surface added by AR-201, what is frozen and what is not.

## 1. Stability

| Surface | Status |
|---|---|
| CLI subcommands, arguments, exit codes, output text, stage/gate names, packet formats | **frozen compatibility surface** (unchanged except the additive `approve-gate` command and the optional `--migrate`, `--reviewer-identity`, `--kind`, `--migrate` flags) |
| `ariadne-run.json` file schema `1` | **frozen** |
| Record contracts inside the state (approval, review, transition, migration records) | **provisional**; each record carries `schema_version: 2` and readers accept `1..2` |
| `src/ariadne_engine/api.py` signatures | **provisional** until AR-203 compatibility tests exist |
| `src/ariadne_engine/{contracts,persistence,statemachine,policy,review}.py` internals | internal; the module paths and public function names are stable, the details may change |

## 2. Loading

No installation and no packaging change: the runtime loads the engine from the same
checkout.

```python
import importlib.util
spec = importlib.util.spec_from_file_location("ariadne_runtime", "scripts/ariadne.py")
runtime = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runtime          # register before exec (the module binds itself)
spec.loader.exec_module(runtime)
api = runtime.ENGINE_API
```

`runtime.PERSISTENCE`, `runtime.POLICY`, `runtime.REVIEWS`, `runtime.STATEMACHINE`,
`runtime.CONTRACTS` expose the engine modules; `runtime.ENGINE_API` is the bound API.

## 3. `Result`

```python
@dataclass(frozen=True)
class Result:
    exit_code: int          # 0 success, 1 refusal/contract error, 2 paused/needs-human
    message: str            # exactly the operator text the CLI writes to stdout
    artifacts: tuple[str, ...]
    state_changed: bool
    @property ok -> bool    # exit_code == 0
```

`api.format_result(result)` returns `result.message` unchanged, so a caller can reproduce
the CLI output byte for byte (`sys.stdout.write(format_result(result))`).

Refusals follow the CLI contract: a runtime error raised by the underlying command becomes
a `Result` with `exit_code=1` and a message beginning `STOPPED: `. Unexpected exceptions
(bugs) propagate. No API call writes to stdout itself; captured text is returned in the
result (and re-emitted only if an unexpected exception escapes, to preserve CLI
interleaving).

## 4. Operations

| Function | Purpose | Notes |
|---|---|---|
| `start_run(project=None, run_root=None, request=None, request_file=None, reasoner=None, adopt_existing=False, run_id=None)` | create a run and the S1 packet | |
| `status(run_root=None, project=None, as_json=False)` | inspect the run | |
| `approve_gate(gate=None, run_root=None, project=None, identity=None, note=None)` | record a human gate decision | the only way to satisfy G1/G2/G3 |
| `prepare_next(run_root=None, project=None, **options)` | propose and prepare the next boundary | `stage`, `retry`, `escalate`, `worker_role`, `motion`, `assets`, `target`, `lenses`, `provider`, `references_file`, … |
| `record_result(run_root=None, project=None, **options)` | record structurally verified same-session outputs | `status`, `provider`, `model`, `summary`, `file` |
| `ingest_return(run_root=None, project=None, input=…)` | store a structured implementation return | |
| `validate_worker(run_root=None, project=None, timeout=120)` | run the independent validation | |
| `prepare_review(run_root=None, project=None, target=None, lenses=None)` | prepare the isolated review boundary | |
| `ingest_review(run_root=None, project=None, input=…, reviewer_identity=…, kind=None)` | record an evidence-bound review | identity required at runtime; `kind` ∈ {experience, technical} |
| `record_acceptance(run_root=None, project=None, outcome=…)` | record the human acceptance outcome | `outcome` ∈ {accepted, rejected} |
| `recovery_report(run_root=None, project=None)` | inspect interrupted work | returns JSON in `message`; exit 2 when `diverged` |

Every function accepts `args=<argparse.Namespace>` to reuse an already-parsed command line
(this is how the CLI delegates); when omitted, the keyword options are used.

## 5. Structured errors

| Error (`ariadne_engine.contracts`) | Raised when | CLI/API result |
|---|---|---|
| `ContractError` | malformed request or artifact; nothing changed | exit 1, `STOPPED: …` |
| `StaleSchema` | a stored schema version cannot be read, or a legacy state needs `--migrate` | exit 1, `STOPPED: Run state schema is unsupported` or the migration instruction |
| `InvalidTransition` | the requested change is not in the transition table | exit 1, names both states |
| `PolicyRefusal` | structurally legal but a precondition fails; carries `problems` | exit 2 from the command that pauses, or exit 1 where the command raised before |
| `UnauthorizedApproval` | an approval is requested or used outside its authorized scope | exit 1, names the gate, channel, subject or revision |

## 6. Engine module entry points (stable names)

* `contracts`: `SCHEMA_RUN`, `SCHEMA_RECORD`, `READABLE_RUN_SCHEMAS`,
  `READABLE_RECORD_SCHEMAS`, `ENGINE_CONTRACT`, `APPROVAL_CHANNEL_HUMAN`,
  `GATE_SUBJECT_TYPES`, `REVISION_FIELDS`, `Subject`, `Approval`, `TransitionRequest`,
  `ReviewRecord`, `digest_fields`, `approval_problems`, `approval_gate_problems`,
  `review_problems`.
* `persistence`: `STATE_NAME`, `state_path`, `load_state`, `write_state`, `migrate`,
  `migrate_file`, `backup_state`, `migration_record`, `needs_migration`, `state_problems`,
  `recovery_report`, `bind_logger`.
* `statemachine`: `STAGE_TRANSITIONS`, `WORKER_LIFECYCLE_TRANSITIONS`,
  `apply_transition`, `assert_transition`, `current_stage`, `lifecycle_of`,
  `worker_transition_for`.
* `policy`: `bind`, `design_direction_subject`, `handoff_subject`, `review_subject`,
  `approve`, `approvals`, `gate_satisfied`, `highest_gate`,
  `creative_evidence_problems`, `g1_problems`, `g2_problems`, `preflight_problems`,
  `validation_problems`, `review_requirements_problems`, `continuation_problems`,
  `repair_allowed`, `retry_problems`, `design_thesis`,
  `markdown_section_body`, `section_raw`, `sha256_file`.
* `review`: `independence_problems`, `evidence_available`, `review_evidence_problems`,
  `required_review_problems`, `build_record`, `store`, `current_review`, `REQUIRED_EVIDENCE`.

## 7. Behaviour a caller can rely on

* A gate is satisfied only by the latest approval for that gate, on `human-cli`, bound to
  the current subject revision, and not consumed by the requested operation.
* A refused operation returns exit code 1 or 2 and leaves `state_changed == False`.
* Every state write is atomic; `state_changed` is computed from the state file digest.
* `record_acceptance --outcome accepted` requires both a review record for the packet and a
  G3 approval bound to it, and consumes that approval.
* `prepare_next` and `advance` apply the same precondition set for the same transition.
