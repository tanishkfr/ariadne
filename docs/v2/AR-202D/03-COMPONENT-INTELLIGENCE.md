# AR-202D — Component intelligence

Source: `src/ariadne_engine/components.py`. Contract:
`contracts.component_candidate_problems`.

## 1. The ladder is preserved

`components.COMPONENT_LADDER`, in order, is the existing minimum-solution ladder:

1. `existing-project-component` — an existing project component already solves it
2. `existing-design-system` — the project's design system already provides it
3. `native-platform` — the platform or browser provides it
4. `project-local-implementation` — small enough to implement locally
5. `approved-dependency` — an already-approved dependency provides it
6. `approved-registry` — an approved registry/component source provides it
7. `new-external-dependency` — no earlier rung solves the need

A candidate is evaluated at the **first rung that actually solves the need**. The
default order is unchanged from AR-200, and the module never jumps to installing
libraries: nothing in it can install, download, resolve or write anything.

## 2. The evaluation record

Every meaningful decision records:

| Field | Enforced |
|---|---|
| `need` | non-empty, in the project's own terms |
| `capability` | what capability the need requires |
| `rung` + `rung_rule` | one of the seven, with the reason that rung exists |
| `candidate` | the named candidate |
| `alternatives` | **at least one** named alternative and why it lost |
| `existing_equivalent` | the check, recorded — `checked: false` requires a reason |
| `findings` | explicit verdicts, never invented numbers |
| `registry` | registry id, queried entry, `checked_on`, freshness window |
| `approval_required` | true on every dependency rung |
| `install_authority` | always `none — human G2 required` |
| `decision` | `selected` / `rejected` / `deferred` / `blocked` |

"One candidate is not a comparison" is enforced: an evaluation with no
alternative is refused.

## 3. Findings, not scores

Ten findings may be recorded — `project_compatibility`,
`design_system_compatibility`, `accessibility`, `dependency_weight`, `licence`,
`framework_compatibility`, `maintenance_risk`, `customisation_requirements`,
`visual_fit`, `interaction_fit` — each with a verdict of `verified`, `claimed` or
`unknown` and, unless the verdict is `unknown`, a reason. A non-`unknown` verdict
without a reason is refused: the record may not assert what it cannot explain.

Unrecorded findings stay `unknown` and are **reported as unknown**, not assumed
benign.

## 4. Blocking rules

On the dependency rungs (`approved-dependency`, `approved-registry`,
`new-external-dependency`), an `unknown` verdict on `licence`,
`project_compatibility` or `framework_compatibility` blocks the candidate. A
dependency whose licence nobody established cannot be adopted by default; that is
where an optimistic default is most expensive.

The rule is deliberately scoped to dependency rungs: a project component or a
native platform feature has no licence question, and demanding one there would
invent a requirement the project does not have.

Two further blocks exist:

* `approved-dependency` requires the name to appear in the declared approved
  dependency list, so an approval cannot be borrowed from a *different*
  dependency — and the record marks that list `approved_dependencies_source:
  "declared-by-caller"`, because it is the caller's declaration rather than
  something the engine verified;
* a cited `approval_id` must name an approval record the engine actually holds.
  `components.approval_record` matches the id against `state["approvals"]`, the
  candidate records `approval_source` (`recorded` / `unverified` / `none`), and an
  id that matches nothing leaves the candidate `blocked`. An authorization id is a
  claim like any other, so it is checked rather than trusted;
* `approved-registry` / `new-external-dependency` must cite a registry entry (or
  an explicit unregistered reason), so a dependency cannot appear without
  provenance.

In this environment the only recorded approval available to a dependency rung is
the human `G2` handoff approval, because AR-201/AR-202D define no
dependency-specific approval subject. A dependency therefore stays `blocked` until
a human records that gate — which is the honest state of affairs, and exactly what
"a recommendation is not installation authority" means in practice.

A blocked candidate is never silently treated as selected, and
`components.dependency_problems` surfaces every blocked dependency for a task so a
stage boundary can report it.

## 5. Registry adapters

Two implementations, both read-only:

* `LocalCapabilityRegistry` — the repository's own
  `references/capabilities.json`, the same registry the creative-intelligence
  capability plan already uses. It validates schema version, a real `checked_on`
  date, a positive freshness window and the entry shape, and reports staleness.
* `FixtureRegistry` — deterministic metadata for tests and benchmarks.

No live registry is contacted, and a registry call installs nothing. The record
keeps the registry id, the queried name, the entry, the `checked_on` date and the
freshness window, so a later reviewer can tell when the metadata was true.

## 6. shadcn, Radix and other registries

shadcn and Radix are candidate ecosystems in the existing capability registry —
not defaults, and not rules. There is no `always use shadcn` and no `Radix is
always preferred` anywhere in the milestone:

* if the project has a mature design system, rung 2 wins before any registry is
  consulted;
* if a native element solves the problem well, rung 3 wins;
* if adding a dependency requires human approval under Ariadne policy, that gate
  is preserved — the evaluation returns `approval_required: true` and
  `decision: blocked`, and `install_authority` is human-only;
* no package installation is ever run by Ariadne, and no test depends on live
  registry availability.

## 7. A recommendation is not permission

The record's `decision` describes the *evidence*: the candidate is the smallest
solution and its known obligations are satisfied. Authorization stays where it was
in AR-201: a new dependency needs a human `G2` approval, and the design-direction
gate (`G1D`) never substitutes for it. A worker may suggest a dependency; the
engine will not act on the suggestion.

## 8. Failure kind

`COMPONENT_INCOMPATIBLE` → `CAPABILITY_FAILURE` (strategy change allowed, no blind
retry), with the blocking findings named in the failure detail.
