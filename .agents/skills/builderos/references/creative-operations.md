# Post-G1 creative operations runtime contract

Read this after G1 is locked and before S4B is delivered. Canonical design and
QA documents still own decisions and quality policy; the project-local ledger
records trace and evidence only.

Run `builderos.py operations-plan --project <project>` to derive approved
requirements and a project-specific visual-QA plan in
`.builderos/creative-operations.json`. The controller also does this
automatically when it prepares S4B.

Record one event or `{"events": [...]}` with:

```text
python <builder-os>/scripts/builderos.py record-operations --project <project> --input <events.json>
```

Supported event types are:

- `implementation`: map an approved requirement to a real source path and anchor;
- `visual-evidence`: record `code-suggests`, `rendered`, `observed`, `verified`, or `unverified` evidence;
- `drift`: classify a difference as `approved`, `allowed`, `drift`, or `unknown` using evidence IDs;
- `creative-review`: record the ten-dimension judgement and one highest-value action after rendered evidence exists;
- `social-strategy`: record an explicitly requested, project-aware strategy and its evidence artifact.

Use [visual-qa.md](../../../../skills/visual-qa.md),
[creative-review.md](../../../../skills/creative-review.md), or
[social-strategy.md](../../../../skills/social-strategy.md) for the event-specific
method. Run `builderos.py operations-check --require plan|implementation|visual|review|social`
for the evidence level being claimed before relying on the ledger.

An `unverified` observation is valid when it names the environmental blocker.
No event grants G1-G5, changes approved design, or proves external provider
behaviour by itself.
