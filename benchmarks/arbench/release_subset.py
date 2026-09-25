"""The curated AR-205 release-gate subset of the exhaustive benchmark suite.

The full suite stays the authority; this list is the fast gate that a release
must pass. It covers critical invariants from every capability area and every
AR-205 group. Run: python benchmarks/run_benchmarks.py --release
"""

RELEASE_SUBSET: tuple[str, ...] = (
    # repository and distribution suites
    "suite.repo-contract",
    "suite.distribution-lifecycle",
    "suite.release-bundle",
    # core lifecycle, authorization and migration invariants
    "lifecycle.start-creates-verified-s1",
    "lifecycle.independent-validation-executes",
    "lifecycle.approval-stale-after-edit",
    "lifecycle.approval-channel-required",
    "lifecycle.schema-migration-explicit",
    "lifecycle.recovery-reports-interrupted-work",
    "security.gate-forgery-in-agents-md",
    "security.review-record-required",
    "security.migrated-legacy-gate-refused",
    "routing.authorization-failure-cannot-be-routed-around",
    "recovery.refuses-ambiguous-orphan",
    "recovery.quarantines-interrupted-write",
    # design intelligence
    "design-direction.worker-cannot-self-approve",
    "design-critique.review-without-rendered-evidence-refused",
    # verification and the decision plane
    "false-acceptance.fabricated-verification-evidence-refused",
    "render-verification.reproduction-must-be-a-new-artifact",
    "decision-plane.cannot-authorize-a-protected-action",
    "decision-plane.invalid-answer-refused-not-coerced",
    # economics safety
    "economics-accounting.unknown-usage-stays-unknown",
    "orchestration-economics.cost-cannot-bypass-policy",
    # distribution guards
    "distribution.uninstall-and-rollback-guards",
    "distribution.release-tooling-offline",
    # AR-205 release metadata and artifacts
    "release-metadata.version-surfaces-agree",
    "release-metadata.manifest-matches-version",
    "release-metadata.distribution-name-decision-recorded",
    "release-distribution.artifacts-match-manifest",
    "release-distribution.experiments-remain-opt-in",
    # AR-205 migration
    "migration.dry-run-writes-nothing",
    "migration.apply-is-additive",
    "migration.repeated-apply-writes-nothing",
    "migration.rollback-refuses-after-v2-work",
    "migration.evidence-report-is-durable",
    # AR-205 integration contract
    "integration-contract.negotiation-outcomes",
    "integration-contract.adapter-envelope",
    "integration-contract.no-authority-from-extra-fields",
    "integration-contract.adapter-cannot-fabricate-validation",
    # golden workflows
    "golden-workflows.mechanical-task",
    "golden-workflows.protected-task",
    "golden-workflows.failure-repair",
    "golden-workflows.design-chain",
    "golden-workflows.decision-plane",
    "golden-workflows.migration-cli",
    # AR-205D decision intelligence
    "decision-compiler.deterministic-fact-wins",
    "decision-compiler.unresolved-never-silently-generative",
    "decision-graph.protected-human-boundary-holds",
    "decision-graph.invalidation-cascades",
    "decision-batching.dependent-question-is-staged",
    "decision-cache.miss-on-model-version-change",
    "decision-cache.stale-and-revoked-are-refused",
    "decision-escalation.human-policy-wins-over-confidence",
    "decision-integrations.evidence-relevance-cannot-elevate-stale",
    "golden-workflows.d1-code-knows",
    "golden-workflows.d5-cache-invalidation-on-relevant-change",
)
