# Live Intelligence Qualification — Ariadne 2.4C

**Purpose:** close the 2.4B evidence gap with a bounded live comparison, without
turning one run into a model ranking or a token/cost claim.

## 1. Environment (re-probed 2026-11-12)

| Surface | Version | Authentication observation | Used in this pass |
|---|---|---|---|
| Command Code CLI | 1.88.5 | existing Command Code subscription; a live task executed | yes, route `command-code` |
| OpenCode CLI | v2.2.5 | configured provider `commandcode`; live task executed | yes, route `opencode` |
| Codex CLI | 0.166.0 | `codex login status` reports ChatGPT login | not run (bounded pass) |
| Claude Code | 2.1.245 | `claude auth status` reports `loggedIn: false` | no |
| Cursor agent CLI | not installed | `UNKNOWN` | no |

Command Code and OpenCode were configured to the same model family,
**DeepSeek V4.1 Flash**, through different harnesses. The comparison is therefore
an **execution-route comparison**, not a model-intelligence comparison. Codex
would have been a different model (`gpt-6.1-terra` in its local config), but it
was not used in this bounded pass and no claim is made about it.

The engine observed only what it could record: the adapter invocation, the
harness's return text, and the execution record. Provider/model identity in the
execution record is `REQUESTED`/harness-configured; no provider supplied a
`PROVIDER_OBSERVED` identity. That is recorded as a limitation, not upgraded.

## 2. Workloads

Six workload families, generated as disposable projects under the qualification
root. Every route received the same files, starting commit, request, scope and
validation command.

| ID | Family | Request shape | Validation |
|---|---|---|---|
| simple | simple bug repair | quote fields containing commas in `export.py` | `pytest -q` |
| multi | multi-file repair | multiply price by quantity across `pricing.py` and `orders.py` | `pytest -q` |
| feature | feature | add an optional CSV header row without changing callers | `pytest -q` |
| refactor | refactor | share one CSV formatter while preserving output | `pytest -q` |
| context-heavy | context-heavy repository analysis | fix `src/app/report.py` in a 25-module package | `pytest -q` |
| ui | UI/accessibility repair | contrast, keyboard focus, inline validation, dialog focus, narrow layout | `pytest -q` |

A matched `context_reduction=adaptive` comparison was run for `context-heavy` and
`ui` on both routes. `off` runs came from the main matrix; `adaptive` runs used
the same project template, request, scope and validation.

The task contract's validation command names the interpreter absolutely
(`<venv>/python -m pytest -q`) so a host `PATH` difference cannot masquerade as a
model failure.

## 3. Results

Every cell is one real `task-start` + `task-run --adapter` execution with
`--max-attempts 1`. A `VALIDATED_NO_PROOF` cell passed the engine's independent
validation but stopped at the review boundary (the UI and refactor families require review);
that is not a failure and no proof is claimed for it.

### 3.1 Route matrix

| Route | Cells | Validated | Proof accepted | Validation failed | Repairs |
|---|---:|---:|---:|---:|---:|
| Command Code | 8 | 8 | 5 | 0 | 0 |
| OpenCode | 8 | 8 | 5 | 0 | 0 |

Four UI cells (off and adaptive on both routes) and two refactor cells end at
the review boundary with no proof receipt. The remaining ten cells produced
`VP-0001` `ACCEPTED`.

The elapsed times ranged from about 75s to 354s. They include model latency,
harness startup, browser-free validation and the engine's bookkeeping. They are
not a controlled speed comparison: the same route varied by more than 2× across
workloads, and the sample is one trial per cell.

### 3.2 Adaptive context

The `ui` workload declares three explicit scope files; the request names the
behaviour but not every file path. The `context-heavy` workload declares 28
explicit files; the request names only `src/app/report.py`.

| Route | Workload | Off packet | Adaptive packet | Saved | Required omitted | Validation off/adaptive |
|---|---|---:|---:|---:|---|---|
| Command Code | ui | 43,333 B | 39,400 B | 3,933 B (9.1%) | none | passed / passed |
| OpenCode | ui | 43,297 B | 39,376 B | 3,921 B (9.1%) | none | passed / passed |
| Command Code | context-heavy | 42,714 B | 39,065 B | 3,649 B (8.5%) | none | passed / passed |
| OpenCode | context-heavy | 42,654 B | 39,037 B | 3,617 B (8.5%) | none | passed / passed |

The exact rows, including `included_bytes`, `omitted_bytes`, `required_omitted`
and evidence paths, are in
`validation/runs/2.4c/live/results.json` (copied from the isolated evaluator).
Packet bytes are a delivery measurement, not a token count.

### 3.3 What the comparison establishes

- Both configured routes can execute the same six bounded workloads on this host.
- The engine's independent validation accepted every completed cell.
- Ten cells reached an ACCEPTED Proof Receipt; six stopped at the review
  boundary because the workload required review and no review adapter was
  supplied; none fabricated a proof.
- Adaptive context omitted only optional unnamed scope files on the `ui`
  workload, saved about 9% of packet bytes, and did not omit a required source.
- No provider supplied token or cost usage. Those fields remain `UNKNOWN`.
- The recorded provider/model identity is harness-configured, not
  provider-observed.

### 3.4 What it does not establish

- No model ranking. Two routes on the same model family are a route comparison;
  a single Codex sample was not run.
- No token, prompt-cache, billing or quota saving.
- No statistical significance. One trial per cell cannot separate model variance
  from harness variance.
- No claim that a faster cell is a better route: workload difficulty, model
  latency and harness startup are not controlled.
- No claim about macOS, Linux or a different browser/host.

## 4. Routing decision

The 2.4B protections remain in force:

- `model_routing=off` by default; `shadow` only records advice.
- minimum eight qualified samples for a promotion;
- current, benchmark-qualified evidence with observed identity;
- a recorded human promotion;
- a degraded or unavailable baseline;
- a qualified alternative and deterministic fallback.

This pass produced **no benchmark-qualified record with eight samples** (one
trial per cell), and no observed provider identity. Therefore:

- **Recommendation:** keep the existing deterministic route.
- **Promotion eligibility:** none.
- **Shadow-mode status:** advisory only; no production route changed.
- **Correct outcome:** "no routing change justified", not "routing failed".

## 5. Harness regression found and repaired

Command Code 1.88.5 withholds edit/write tools from headless runs unless they are
enabled explicitly. The 2.4A preset did not pass `--tools-all`, so the first
live cell was refused by the harness's own permission gate. The adapter preset
now includes `--tools-all`; the engine's independent validation and scope check
remain the boundary. This is a harness repair, not a model result, and is
recorded separately from the comparison.

OpenCode produced one malformed return in an early cell (unfilled template) and
one out-of-scope change under an earlier directory-style scope. The malformed
return was refused; the scope issue was corrected to explicit paths and the
workload re-run. Those are execution/harness outcomes, not hidden passes.

## 6. Evidence

- `scripts/evaluate-live-intelligence.py`
- `validation/runs/2.4c/live/environment.json`
- `validation/runs/2.4c/live/results.json`
- `validation/runs/2.4c/live/cells/` (per-cell project, run state, logs)
- `validation/runs/2.4c/live/2.4c-live-*.log` (retry and context-heavy runs)
- `docs/v2/2.4/MODEL-ROUTING-EVALUATION.md` (policy and promotion rules)
