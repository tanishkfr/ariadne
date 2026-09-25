# AR-200 / 09 — AR-201 HANDOFF

Implementation-ready specification for the first vertical slice. Read `03-ARCHITECTURE.md` §2–§4 and `04-EXTRACTION-PLAN.md` §B (H1, H2, H5) first; they are normative for this work.

## 0. Starting point

| Item | Value |
|---|---|
| Worktree | `<path>` |
| Branch | `v2/ar-200-baseline` (continue on it, or branch `v2/ar-201-core` from it) |
| Base commit | `5819dae3cb8f216dac3abc77bd8429a4a73a4343` |
| Runtime under test | `scripts/ariadne.py` (5 785 lines), `scripts/prepare-stage.py` (2 600), `scripts/reasoners.py` (406) |
| Benchmark | `python benchmarks/run_benchmarks.py` — must be green at the end (0 fail, 0 error) |

**Read first, in this order** (all in this worktree):

1. `scripts/ariadne.py:261-271` — `load_state`, `RUNTIME_SCHEMA` (line 40). Where the schema gate lives.
2. `scripts/ariadne.py:905-915` — `project_runtime`: how a gate is currently read (the defect).
3. `scripts/ariadne.py:2795-2852` — `record_acceptance`: how G3 is currently enforced.
4. `scripts/ariadne.py:3265-3478` — `advance`: the multi-path preconditions (the inconsistency).
5. `scripts/ariadne.py:3481-3536` — `infer_next_stage`: the only place the stage chain is decided.
6. `scripts/ariadne.py:3539-3750` — `prepare_next`: the continuation path with its own preconditions.
7. `scripts/ariadne.py:2668-2694` and `2705-2792` — review validation and ingestion (the attestation defect).
8. `scripts/prepare-stage.py:1657-1810` — `verify_packet`: the invariants that must keep working.
9. `benchmarks/arbench/cases.py` — the three failing cases that define success.
10. Boreal (read-only reference, do not copy files): `design_harness\model.py:47-69`, `183-187`, `264-278`, `383-389`; `design_harness\engine.py:321-335`, `770-880`.

## 1. Deliverables (exact)

Create these modules. Move logic; do not rewrite it.

### `src/ariadne_engine/__init__.py`
Package marker, `__version__` from the same source as `src/ariadne/__init__.py` (`metadata.version("ariadne")` with the `VERSION`-file fallback).

### `src/ariadne_engine/contracts.py`
```python
SCHEMA_RUN = 2                      # the schema this runtime WRITES
READABLE_RUN_SCHEMAS = (1, 2)       # the schemas it can READ (v1 is the current on-disk schema)

@dataclass(frozen=True)
class Approval:
    schema_version: int
    approval_id: str                # "apv_<utc>_<8hex>"
    gate: str                       # "G1".."G5"
    subject_type: str               # "design-direction" | "handoff" | "review"
    subject_id: str                 # e.g. packet id
    revision_hash: str              # sha256 over the declared fingerprint fields
    identity: str                   # operator-supplied label, recorded verbatim
    channel: str                    # only "human-cli" satisfies a gate
    note: str
    recorded_at: str

@dataclass(frozen=True)
class TransitionRequest:
    kind: str                       # "stage" | "worker-lifecycle"
    to: str
    reason: str
    evidence: tuple[str, ...]       # ids/paths the caller believes justify the move
```

`revision_hash` must be computed from a *declared field list*, not from the file bytes — copy the pattern at Boreal `model.py:183-187,264-278`:
- `design-direction`: the `DESIGN.md` design thesis line (use the existing `design_thesis` helper, `ariadne.py:778-785`) + the requirement ids in `.ariadne/creative-operations.json`;
- `handoff`: `INVESTIGATED` — reuse `TRANSPORT.worker_contract(handoff_text)["scope_rows"]` plus the handoff file's sha256;
- `review`: the S5 `packet_sha256`.
Rationale for a declared-field hash rather than raw bytes: cosmetic edits must not silently invalidate an approval, but semantic edits must. Keep the field list small and documented in the module docstring.

### `src/ariadne_engine/persistence.py`
```python
def load_state(run_root: Path) -> dict          # raises StaleSchema (typed) if unreadable
def write_state(run_root: Path, state: dict) -> None   # temp file + replace_with_retry (reuse)
def migrate(state: dict, from_version: int, to_version: int) -> dict  # ordered, pure, recorded
def migration_record(state: dict) -> dict       # what was migrated, when, from→to
```
Rules: unknown schema ⇒ refuse (current behaviour preserved); readable older schema ⇒ migrate **only** when `--migrate` is explicit, backing up `ariadne-run.json` to `ariadne-run.v<n>.bak` and appending a migration entry into `state["migration_history"]` and the event log; never migrate implicitly on read.

### `src/ariadne_engine/statemachine.py`
```python
STAGE_TRANSITIONS: frozenset[tuple[str, str | None]]     # from 03 §3
WORKER_LIFECYCLE_TRANSITIONS: frozenset[tuple[str, str]] # from ariadne.py:203-247 (worker_outcome)

def assert_transition(kind: str, current: str, target: str) -> None   # raises InvalidTransition
def apply_transition(state: dict, request: TransitionRequest, *, permitted: bool) -> dict
```
`apply_transition` is the **only** function that may write `state["packets"][-1]`, the worker `lifecycle`, `implementation_state`, `validation_state`, `review_state` or `acceptance_state`. Refuse any transition not in the table, with the reason string preserved verbatim for the operator.

### `src/ariadne_engine/policy.py`
```python
def gate_satisfied(state: dict, gate: str, subject: dict) -> tuple[bool, str]
def approve(state: dict, gate: str, subject: dict, identity: str, note: str) -> dict   # appends Approval
def approval_problems(approval: dict, subject: dict) -> list[str]                     # binding + channel
def scope_problems(...)        # moved from prepare-stage.py:336-431 / 451-589 (do not re-implement)
def repair_allowed(state: dict) -> tuple[bool, str]
def continuation_problems(state: dict, target_stage: str) -> list[str]   # the single precondition set
```
`gate_satisfied` requires: an `Approval` for that gate; `channel == "human-cli"`; `revision_hash == revision_hash(subject, now)`; and no later edit to the subject. The `AGENTS.md`/`DESIGN.md` gate fields remain as human-readable mirrors written **after** approval; they are never read for enforcement.

### `src/ariadne_engine/api.py`
```python
def start_run(project, run_root=None, request=None, request_file=None, reasoner=None, adopt_existing=False) -> Result
def status(run_root=None, project=None) -> Result
def approve_gate(gate, run_root=None, project=None, identity=None, note=None) -> Result     # NEW command
def prepare_next(run_root=None, project=None, **options) -> Result
def record_result(run_root=None, project=None, **options) -> Result
def ingest_return(run_root=None, project=None, input=None) -> Result
def validate_worker(run_root=None, project=None, timeout=120) -> Result
def prepare_review(run_root=None, project=None, target=None, lenses=None) -> Result
def ingest_review(run_root=None, project=None, input=None, reviewer_identity=None) -> Result
def record_acceptance(run_root=None, project=None, outcome=None) -> Result
```
`Result` is a small frozen record: `exit_code`, `message`, `artifacts: tuple[str, ...]`, `state_changed: bool`. All existing `print` output moves behind a `format_result(result) -> str` so the CLI text stays identical.

## 2. Modification rules

1. **`src/ariadne_engine/*` is new code built by moving existing functions.** When a function moves, its self-tests move with it and the original call site delegates. Do not leave two implementations.
2. **`scripts/ariadne.py` keeps every subcommand name and the exit codes 0/1/2.** Add exactly one new subcommand: `approve-gate`. Update `parser()` (`ariadne.py:5498-5739`) and the dispatch map (`ariadne.py:5747-5774`).
3. **`scripts/prepare-stage.py` must not change its packet format, manifest keys or verification semantics.** Adding a memo/backing field is allowed only in AR-202.
4. **`scripts/check.py` must stay green.** It asserts command names, distribution tokens, prompt mirrors and links; if it fails, you have broken a public contract.
5. **No file moves or renames** of existing scripts in AR-201. The public runtime layout is frozen.
6. **Do not enable implicit migration.** Migration requires an explicit flag.
7. **Do not delete the `AGENTS.md`/`DESIGN.md` mirror fields.** Write them when an approval is granted so humans still see them; ignore them for policy.

## 3. Task list (ordered, each with its verification)

| # | Task | Verification |
|---|---|---|
| T1 | Create `contracts.py` + `persistence.py` with schema 2 written / 1+2 readable, no implicit migration | `python benchmarks/run_benchmarks.py --case lifecycle.state-schema-mismatch-refused` still passes; new `lifecycle.migration-readable-schemas` passes |
| T2 | Move the stage/worker transition tables into `statemachine.py`; route `advance`, `prepare_next`, `validate_worker`, `finish_worker_validation`, `ingest_review`, `record_acceptance`, `record_reasoner_failure` through `apply_transition` | all 16 `lifecycle.*` cases pass; new `lifecycle.invalid-transition-refused` passes |
| T3 | Implement `policy.gate_satisfied` + `approve_gate` command; write the mirror fields on approval | `security.gate-forgery-in-agents-md` **flips to pass**; new `lifecycle.approval-stale-after-edit` and `lifecycle.approval-channel-required` pass |
| T4 | Single precondition set: `continuation_problems(state, target)` used by `advance` and `prepare_next` (and the `--migrate` gate for schema) | `security.creative-gate-bypass` **flips to pass** |
| T5 | Evidence-bound review: `ingest_review` requires `--reviewer-identity`, records `context_digest` = S5 packet sha256, and refuses when the identity equals the worker identity recorded in run state; keep the existing structural checks and the attestation line as a secondary (non-sufficient) signal | `security.review-attestation-unverified` **flips to pass**; existing review self-tests in `ariadne.py --self-test` still pass |
| T6 | `api.py` + CLI delegation; `format_result` preserves output text | `suite.runtime-self-test` 125/125; `suite.transport-self-test` 50/50; `suite.repo-contract` 18 ok; `suite.repo-self-test` PASS |
| T7 | Add the four new benchmark cases to `benchmarks/arbench/cases.py` and regenerate `manifest.json` | `python benchmarks/run_benchmarks.py --write-manifest`; full run: 0 fail, 0 error |

## 4. Required new benchmark cases (write them first, watch them fail, then fix)

```python
lifecycle.approval-stale-after-edit
    task: approve G1 via `approve-gate`; then change the design thesis in DESIGN.md; call prepare-next
    expect: exit != 0, no S4A packet, refusal names the stale approval

lifecycle.approval-channel-required
    task: write an Approval record by hand (or via the worker-equivalent path) with channel != "human-cli"
    expect: gate not satisfied; no S4A packet

lifecycle.migration-readable-schemas
    task: start a run, downgrade a copy of the state to schema 1, run `status` (expect refusal without --migrate),
          then run with `--migrate` against the sandbox copy
    expect: refusal is explicit; migration writes <name>.v1.bak, records migration_history, and status then succeeds

lifecycle.invalid-transition-refused
    task: invoke prepare_next with an explicit stage that the state does not permit (e.g. S4A while at S1)
    expect: refusal from the choke point with a typed message (existing behaviour must be preserved verbatim)
```

Case expectations must be phrased as integrity requirements (see `benchmarks/arbench/cases.py` header) so a `fail` always means a real defect.

## 5. Stop conditions

Stop and report instead of continuing if any of these occur:

1. **Schema migration would modify an existing run outside the sandbox** — never migrate a real project's state; refuse and report.
2. **An existing deterministic suite would have to change** to make a new behaviour pass (`check.py` contract, `ariadne.py --self-test`, `prepare-stage.py --self-test`). Changing a shipped test to fit new code is a compatibility break, not a fix.
3. **A packet-format or manifest-key change appears necessary.** That is AR-202 scope; report and stop.
4. **Flipping one of the three security cases requires weakening any hash, scope, immutability or evidence check.** Report the trade-off rather than taking it.
5. **Boreal or any original checkout would need to change.** Prohibited.
6. **The CLI must lose a subcommand, gain a required argument on an existing command, or change an exit code.**
7. **A task cannot be completed without a new third-party dependency.**
8. **Two consecutive full benchmark runs disagree on any case verdict** (non-determinism): report the case and the divergence.

## 6. Definition of done

- `python benchmarks/run_benchmarks.py` → `fail: 0`, `error: 0`; `skip` only for `suite.wheel-install` / `suite.reasoner-rollback` (declared not executable).
- The three previously failing security cases are `pass` with evidence in `results/LATEST.json`.
- `suite.runtime-self-test` (125), `suite.transport-self-test` (50), `suite.repo-contract` (18), `suite.repo-self-test`, `suite.distribution-lifecycle` (55) all unchanged.
- `git status` in the v2 worktree shows only intended files; no writes to `the public export checkout`, `the private canonical repository` (other than the worktree registration), or the Boreal tree.
- A short AR-201 report stating: what moved, the schema change + migration semantics, the exact benchmark delta, and any residual limitation (e.g. approvals are authorization, not isolation).
- No push, no tag, no publish.

## 7. Explicit anti-goals

Do not, in AR-201: add transactions or rollback; add rendered QA; add a live agent adapter; port Boreal modules wholesale; introduce a database, queue, service, or scheduler; change the packet format; rename the distribution; optimise performance; touch the `dh/design-harness-*` branch or any Boreal file; run paid model evaluations.
