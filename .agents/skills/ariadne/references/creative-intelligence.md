# Creative intelligence runtime contract

Read this only while planning or recording S1-S3 creative work. The runtime
owns the JSON schema; canonical Ariadne skills and policies still own method
and quality.

## Assessment

After `PROJECT.md` exists, interpret the project and create a temporary JSON
assessment. Do not classify by keyword counts. Every characteristic needs one of
`low`, `medium`, or `high` and a project-specific reason:

```json
{
  "characteristics": {
    "novelty": {"level": "medium", "reason": "..."},
    "uncertainty": {"level": "medium", "reason": "..."},
    "visual_dependence": {"level": "high", "reason": "..."},
    "technical_uncertainty": {"level": "low", "reason": "..."},
    "domain_complexity": {"level": "medium", "reason": "..."},
    "reference_sensitivity": {"level": "high", "reason": "..."},
    "generic_risk": {"level": "high", "reason": "..."},
    "interaction_complexity": {"level": "low", "reason": "..."},
    "asset_uncertainty": {"level": "low", "reason": "..."},
    "motion_dependence": {"level": "low", "reason": "..."}
  },
  "references_supplied": false,
  "alternatives_helpful": {"value": true, "reason": "..."},
  "social_request": {
    "value": false,
    "request": "the user's exact social-strategy request, or empty"
  },
  "research_questions": [
    {
      "id": "rq-1",
      "question": "A falsifiable, project-specific question",
      "reason": "Why the decision needs this answer",
      "strategy": "What sources or comparisons will answer it",
      "kind": "reference",
      "blocking": false
    }
  ]
}
```

Allowed question kinds: `reference`, `technical`, `domain`, `resource`, `asset`.
An empty question list is correct when research would not change a decision.

Run:

```text
python <ariadne>/scripts/ariadne.py creative-plan --project <project> --input <assessment.json>
```

## Evidence events

Pass one event or `{"events": [...]}` to `record-creative`. Do not invent an
artifact merely to satisfy the schema.

Skill transitions:

```json
{"type":"skill","skill":"reference-analysis","state":"invoked","evidence_path":"<real packet or transcript>"}
{"type":"skill","skill":"reference-analysis","state":"completed","output_path":"<real output>","result":"...","usefulness":"useful"}
{"type":"skill","skill":"reference-analysis","state":"used","downstream_path":"<artifact>","decision_ids":["decision-1"]}
```

Use `usefulness: "not-useful"` when a completed method produced nothing worth
carrying forward. Optional work may be `skipped` with a reason; attempted work
may be `failed` with a reason. Mandatory work cannot be skipped.

An optional method skipped during intake may be activated later only by a new
explicit user request. Preserve the original skip and record:

```json
{"type":"skill-activation","skill":"social-strategy","explicit_request":"the user's request"}
```

This returns the optional method to `recommended`; it still needs separate
`invoked`, `completed`, and `used` evidence. Do not use late activation for a
mandatory method or infer a request from project content.

Reference inspection:

```json
{
  "type":"reference",
  "id":"ref-1",
  "source":"https://example.com",
  "state":"inspected",
  "inspection":"visual",
  "evidence_path":"<retrieved page, screenshot, or provider transcript>",
  "observations":["What was directly observable"],
  "mechanisms":["At most two transferable mechanisms"],
  "why_it_matters":"Why this project needs it",
  "borrow":"What may transfer",
  "reject":"What must not be copied"
}
```

Use `state: "found"` for discovery without inspection. Use
`state: "inaccessible"` with `blocker` and no observations when access fails.

Decision trace:

```json
{
  "type":"decision",
  "id":"decision-1",
  "decision":"The concrete project choice",
  "principle":"What the observation became",
  "basis":"reference",
  "claim_status":"SUPPORTED",
  "reference_ids":["ref-1"],
  "artifact_path":"<DESIGN.md or another real output>",
  "artifact_anchor":"Exact text present in that artifact",
  "status":"proposed",
  "gate":"pending"
}
```

`basis` may be `reference`, `research`, `thesis`, or `constraint`. Record a
reference conflict with two or more IDs and a design implication. Record
multiple direction candidates only when the assessment says they are helpful;
each candidate needs a different mechanism and experience, not a palette swap.

Resource decision:

```json
{
  "type": "resource",
  "id": "resource-observer",
  "name": "Platform observer",
  "category": "browser-api",
  "provides": "Active-section observation without a package",
  "appropriate_because": "The interaction only needs bounded threshold changes",
  "compatibility": "Supported by the inspected target-platform record",
  "license": "N/A - browser platform capability",
  "implementation_cost": "One observer and a deterministic fallback",
  "alternatives": [{"name": "scroll listener", "reason": "More manual event handling"}],
  "necessary": true,
  "decision": "use",
  "claim_status": "SUPPORTED",
  "source_reference_ids": ["ref-platform-doc"],
  "artifact_path": "<RESEARCH.md or HANDOFF.md>",
  "artifact_anchor": "<exact text in that artifact>"
}
```

Allowed categories are `library`, `framework`, `browser-api`, `font`,
`icon-set`, `asset-source`, `image-source`, `technique`, `design-tool`, and
`component-primitive`. Decisions are `use`, `do-not-use`, or `defer`. Every
resource comparison needs at least one inspected source and one named
alternative. This record proposes or rejects a resource; it never installs one
or grants G2.
