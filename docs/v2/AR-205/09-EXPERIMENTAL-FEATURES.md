# AR-205 — 09 — Experimental features (AR-204 flags)

The AR-204 economics work added seven behavior-sensitive settings plus one
evidence-preserving setting. None of them changes what a model sees unless it is
explicitly enabled, and the release gate fails if any default moves.

| Flag | Values | Default | Stability | Risk if enabled | Evidence | Enable | Reset |
|---|---|---|---|---|---|---|---|
| `prompt_profile` | legacy / compact_v2 | legacy | experimental | changed prompt scaffolding can change model behaviour | byte measurements only; no quality comparison | `ariadne economics --prompt-profile compact_v2` | `--prompt-profile legacy` |
| `tool_loading` | legacy / packs | legacy | experimental | a required capability could be omitted if selection is wrong | deterministic schema tests; no quality comparison | `--tool-loading packs` | `--tool-loading legacy` |
| `compaction` | off / structured_v1 | off | experimental | dropped history could contain unresolved work | invariant tests only | `--compaction structured_v1` | `--compaction off` |
| `context_reduction` | off / adaptive | off | experimental | a needed source could be omitted | AR-202 decision records; no quality comparison | `--context-reduction adaptive` | `--context-reduction off` |
| `history_format` | legacy / structured_v1 | legacy | experimental | structured history can alter model behaviour | byte measurements only | `--history-format structured_v1` | `--history-format legacy` |
| `routing_economics` | off / observe | off | experimental | records cost-directed routing suggestions | accounting tests only | `--routing-economics observe` | `--routing-economics off` |
| `packet_order` | legacy / stable_prefix | legacy | experimental | reordered packets can change cache and model behaviour | byte measurements only | `--packet-order stable_prefix` | `--packet-order legacy` |
| `output_externalization` | off / threshold | threshold | stable (evidence-preserving) | none: the full output is still stored and digests are unchanged | digest and retrieval tests | already on | `--output-externalization off` |

## Why nothing was promoted

The AR-204 report explicitly did not execute a live model-quality comparison, and
no paid provider call was authorized in AR-205. A byte reduction is not a
quality result, so all seven behavior-sensitive settings stay at their
pre-AR-204 default in v2.0.0.

## Enforcement

- `release.experimental_defaults_problems()` fails the gate when a
  behavior-sensitive setting is in `SAFE_DEFAULTS` or its default is not the
  conservative value, or when the externalization default changes.
- `efficiency.set_efficiency_config()` refuses unknown setting names.
- Benchmark group `release-distribution` asserts the public defaults.
- The evaluation plan for a future promotion compares legacy and candidate on
  identical tasks, measuring verified completion, total usage, turns, repairs,
  tool errors, latency, context and verification outcome. No such run exists
  yet, so no promotion is claimed.
