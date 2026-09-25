# AR-204 — AR-205 Handoff

Implementation-ready notes for the release and integration milestone. AR-205 was
not started.

## 1. Starting point

| Item | Value |
| --- | --- |
| Branch | `v2/ar-204-harness-economics` |
| Base | `94b40f5d9f79ae24c4fd8033c64b301c59e7cbb8` (AR-203, frozen) |
| Worktree | `<path>` |
| Engine version | unchanged `1.6.7` until AR-205 decides otherwise |
| Run-state schema | still 1; two additive collections, no migration |
| Dependencies | unchanged; standard library only |
| Remote state | untouched: no push, tag, release or publication |

## 2. Surfaces AR-204 added

| Surface | Entry point |
| --- | --- |
| CLI | `ariadne.py economics`, `request-map`, `tool-packs`, and the efficiency settings on `economics` |
| API | fourteen functions from `record_execution_billing` to `set_efficiency` |
| Engine modules | `serialization`, `economics`, `harness`, `tooling`, `artifacts`, `history`, `orchestration`, `efficiency`, `prompting` |
| Run state | `artifacts`, `compaction_records` collections with declared bounds |
| Events | `usage_recorded`, `billing_recorded`, `cache_observed`, `output_externalized`, `history_compacted`, `path_selected`, `efficiency_configured` |

## 3. Flags AR-205 inherits, and their defaults

| Setting | Values | Default | What enabling it changes |
| --- | --- | --- | --- |
| `prompt_profile` | legacy, compact_v2 | legacy | drops and shortens transport scaffolding only |
| `tool_loading` | legacy, packs | legacy | defers unused capability packs |
| `compaction` | off, structured_v1 | off | active history becomes structured |
| `context_reduction` | off, adaptive | off | reserved; AR-202 decisions already run |
| `history_format` | legacy, structured_v1 | legacy | reserved for the transcript format |
| `routing_economics` | off, observe | off | reserved for measured routing |
| `packet_order` | legacy, stable_prefix | legacy | re-orders what a worker reads |
| `output_externalization` | off, threshold | threshold | stores large output instead of dropping it |

Every setting is recorded on the run state with a digest, so a report can always
name the profile that produced it.

## 4. Measurements AR-205 should carry forward

1. Re-run `benchmarks/run_benchmarks.py --only harness-metrics` on the release
   candidate and compare the packet figures against
   `docs/v2/AR-204/measurements/ar-204-measurement-summary.json`.
2. Record at least one control-versus-candidate comparison for `prompt_profile`
   and for `tool_loading` with a live model before either default moves.
3. Add the subagent context-reduction measurement the orchestration report names
   as `UNKNOWN`.
4. Measure both decision shapes — batched and generative — so
   `decision_layer_cost` reports a comparison instead of two unmeasured rows.
5. Optionally implement the ledger projection described below and measure it.

## 5. Ranked opportunities for the next milestone

| Rank | Opportunity | Measured size | Risk | Rollback |
| ---: | --- | ---: | --- | --- |
| 1 | Deterministic projection of the two design ledgers | 22,251 volatile bytes | medium: drops per-entry timestamps from delivered content | flag off by default |
| 2 | Enable capability packs per stage | 107,777 deferrable bytes | medium: a worker may need a deferred declaration | one setting |
| 3 | Enable the compact scaffolding profile | 653 bytes | low structurally, unknown behaviourally | one setting |
| 4 | Enable structured compaction for long transcripts | 7,548 active bytes per 9 entries | medium: behaviour on a long transcript is untested | one setting |
| 5 | Re-order a packet stable-first | not measured as a size change | high: changes what a worker reads | one setting |

The first two are the only ones with a large measured size, and both need a live
evaluation before they become defaults.

## 6. Release-integration notes

* The nine new engine modules ship inside the existing package; `src/ariadne_engine/__init__.py`
  exports them, so a wheel built by the existing tooling picks them up with no
  packaging change.
* The four new CLI commands belong in the README command list and in the release
  notes when AR-205 writes them.
* `docs/v2/AR-204/measurements/` is repository data, not generated at install
  time; it should stay out of the installed skill payload if the distribution
  already excludes `docs/`.
* The artifact directory `evidence/artifacts/` is created lazily inside a run
  root and needs no installation change.
* A price-profile file is optional data. If AR-205 ships one, it must name its
  source and effective date, and the engine must keep treating it as data rather
  than as routing input.

## 7. Constraints that survive

* No paid provider call is required for the milestone's own tests.
* Boreal remains unmodified; its integration belongs to AR-205 and no AR-204
  decision depends on reading it.
* Verification and authorization invariants are unchanged and must remain so: a
  cost optimisation that weakens either is a regression.
* The engine stays provider-neutral: no adapter-specific assumption was added, and
  none is required to adopt the flags above.

## 8. First actions for AR-205

1. Read `12-AR-204-REPORT.md` §6 for the three findings that were reported rather
   than fixed.
2. Decide whether the release candidate enables any flag; the defaults are safe
   and a release with every flag at default is a valid AR-205 starting point.
3. Re-run the full known-good suite from `11-TEST-RESULTS.md` §3 before packaging,
   and keep the repository-contract check green as the new documents become part
   of it.
