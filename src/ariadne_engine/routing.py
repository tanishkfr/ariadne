"""Task characterisation and executable routing (AR-202 T3/T5).

Characterisation is deterministic on purpose. No model call is made to classify
a task, and no numeric score is invented: every characteristic is an ordinal
value (``LOW`` / ``MEDIUM`` / ``HIGH`` / ``UNKNOWN``) that names the evidence it
was derived from and whether it was user-declared, rule-derived or
runtime-observed. When the evidence is absent the value stays ``UNKNOWN``.

Routing turns that characterisation into an *executed* decision:

1. required capabilities come from the characterisation, not from taste;
2. candidates missing a required capability are eliminated first;
3. candidates the policy does not allow (unselectable provider, authority,
   channel) are eliminated next;
4. among the remaining candidates the lightest sufficient one is preferred;
5. escalation is required when difficulty, stakes or failure evidence demands it;
6. a strategy that already failed for the same reason is not repeated;
7. when no authorized candidate remains the route is ``no-route`` and the
   caller pauses instead of guessing.

An authorization refusal and a human gate are never routed around: routing may
only choose *how* authorized work is performed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Mapping

from . import contracts
from .contracts import ContractError

# ------------------------------------------------------------- vocabulary

REASONING_STAGE_CAPABILITY = {
    "S1": "intake",
    "S2": "research",
    "S3": "design-direction",
    "S4A": "handoff",
    "S5": "creative-review",
    "S6": "fresh-task-continuity",
}

WORKER_ROLE_CAPABILITIES = {
    "bulk": ("implementation",),
    "strong": ("implementation", "implementation-repair"),
    "senior-reasoning": ("implementation", "implementation-repair", "escalation"),
}

WORKER_CAPABILITY_IDS = ("implementation", "implementation-repair", "escalation")
"""Capability ids that describe an implementation worker rather than a reasoner."""

DESIGN_CAPABILITY_IDS = (
    "reference-discovery",
    "reference-content",
    "visual-inspection",
    "interaction-inspection",
    "browser-observation",
    "interaction-observation",
    "accessibility-observation",
    "design-critique",
    "component-research",
)
"""Capability ids that describe *evidence production*, not a worker personality.

They are declared by adapters, never inferred from a model name or a vendor, and
they are routed separately from implementation work so a design evidence gap
cannot be mistaken for an unsuitable implementation worker.
"""

EVIDENCE_CAPABILITY_SOURCES: dict[str, tuple[str, str]] = {
    "reference-discovery": ("reference", "discover"),
    "reference-content": ("reference", "retrieve_content"),
    "visual-inspection": ("reference", "inspect_visual"),
    "interaction-inspection": ("reference", "inspect_interaction"),
    "browser-observation": ("capture", "screenshot"),
    "interaction-observation": ("capture", "interaction"),
    "accessibility-observation": ("capture", "accessibility"),
    "component-research": ("registry", "entries"),
    "design-critique": ("critique", "review"),
}
"""Evidence capability -> the adapter family and capability that must declare it.

``design-critique`` is declared here so a future review adapter can announce
itself, but no need in :data:`DESIGN_EVIDENCE_REQUIREMENTS` raises it: critique is
an execution step with its own provenance, not evidence production.
"""


def evidence_vocabulary_problems() -> list[str]:
    """Whether the routing tables use exactly the declared capability vocabulary.

    The vocabulary was previously exported and never consulted, and the two sets
    had already drifted. Routing now refuses to decide with a capability id that
    no declaration can carry, so an id cannot be routed by one table and rejected
    by another.
    """
    declared = set(DESIGN_CAPABILITY_IDS)
    used = set(EVIDENCE_CAPABILITY_SOURCES)
    problems: list[str] = []
    for name in sorted(used - declared):
        problems.append(f"routing uses evidence capability {name!r}, which is not a declared design capability id")
    for name in sorted(declared - used):
        problems.append(f"declared design capability {name!r} has no adapter capability mapping")
    for table_name, table in (
        ("DESIGN_EVIDENCE_REQUIREMENTS", DESIGN_EVIDENCE_REQUIREMENTS),
        ("DESIGN_OPTIONAL_EVIDENCE_NEEDS", DESIGN_OPTIONAL_EVIDENCE_NEEDS),
    ):
        for need, rows in table.items():
            for _characteristic, capability in rows:
                if capability not in declared:
                    problems.append(f"{table_name} need {need!r} names undeclared capability {capability!r}")
    return problems

DESIGN_EVIDENCE_REQUIREMENTS: dict[str, tuple[tuple[str, str], ...]] = {
    "reference-retrieval": (
        ("reference_research", "reference-discovery"),
        ("reference_research", "reference-content"),
    ),
    "reference-visual": (("reference_research", "visual-inspection"),),
    "rendered-observation": (("rendered_qa", "browser-observation"),),
    "rendered-interaction": (("rendered_qa", "interaction-observation"),),
    "accessibility-observation": (("accessibility_review", "accessibility-observation"),),
    "component-research": (("component_research", "component-research"),),
}
"""Design pipeline need -> (characteristic, evidence capability) that must be available.

One table, so a need cannot demand evidence in one place and ignore it in
another. The characteristic names are the ones the characterisation actually
records.

Only capabilities a design task genuinely cannot proceed without are listed here.
Interaction inspection of an external reference is *not*: a reference can be
visually inspected and analysed without ever being driven, and requiring a
driver would block every reference-research task in a normal environment. It is
recorded as an optional opportunity instead (see below).

Independent critique is deliberately *not* in this table: a critique is an
execution step with its own provenance (``critique.prepare_review`` and the S5
boundary requirement), not an adapter that produces evidence. Modelling it as an
adapter here would let a missing review be reported as a missing capability,
which is a different and more actionable failure.
"""

DESIGN_OPTIONAL_EVIDENCE_NEEDS: dict[str, tuple[tuple[str, str], ...]] = {
    "reference-interaction": (("reference_research", "interaction-inspection"),),
}
"""Evidence capabilities that would deepen a design task but never block it.

They are recorded in the routing decision as opportunities, so an operator can
see what a richer environment would add without the workflow refusing to proceed
when it is absent.
"""


def design_evidence_needs(characteristics: Mapping, *, optional: bool = False) -> list[dict]:
    """Which evidence capabilities a design characterisation actually requires.

    Only ``REQUIRED`` raises a need; ``OPTIONAL`` never blocks a route, which is
    what keeps a small design task from demanding research infrastructure it does
    not need.
    """
    values = {
        str(name): str((value or {}).get("value", "UNKNOWN")) if isinstance(value, Mapping) else str(value)
        for name, value in (characteristics or {}).items()
    }
    table = DESIGN_OPTIONAL_EVIDENCE_NEEDS if optional else DESIGN_EVIDENCE_REQUIREMENTS
    needs: list[dict] = []
    for need, sources in table.items():
        for characteristic, capability in sources:
            if values.get(characteristic) == "REQUIRED":
                needs.append({
                    "need": need,
                    "capability": capability,
                    "characteristic": characteristic,
                    "source": "rule-derived",
                    "evidence": f"the task characterisation requires {characteristic.replace('-', ' ')}",
                    "optional": bool(optional),
                })
    return needs


def _adapter_candidates(
    adapters: Mapping,
    family: str,
    *,
    state: Mapping | None = None,
    policy: str = "declared",
) -> list[dict]:
    """Declared adapter capabilities, plus the registry evidence for each.

    The declaration is unchanged; AR-203 adds what the capability registry
    established about it. Without a registry record the status is ``DECLARED``
    when the adapter itself declares the capability and ``UNKNOWN`` otherwise, so
    nothing here turns configuration into verification.
    """
    from . import capabilities as capability_module

    rows: list[dict] = []
    for adapter_id, adapter in sorted(dict(adapters or {}).items()):
        capabilities = set(str(item) for item in adapter.capabilities())
        enabled = True
        if hasattr(adapter, "enabled"):
            enabled = bool(adapter.enabled())
        elif hasattr(adapter, "available"):
            enabled = bool(adapter.available()[0])
        evidence: dict[str, dict] = {}
        for capability in sorted(capabilities):
            if state is None:
                evidence[capability] = {
                    "status": "DECLARED", "freshness": "UNKNOWN",
                    "reason": "the adapter declares this capability; no registry is bound to this route",
                }
            else:
                resolved = capability_module.capability_status(
                    state, family=family, adapter=str(adapter_id), capability_id=capability,
                    declared=sorted(capabilities),
                )
                evidence[capability] = {
                    "status": resolved["status"],
                    "freshness": resolved["freshness"],
                    "reason": resolved["reason"],
                }
        rows.append({
            "id": str(adapter_id),
            "kind": family,
            "capabilities": [
                {"id": capability, "evidence": evidence[capability]["status"].lower()}
                for capability in sorted(capabilities)
            ],
            "capability_evidence": evidence,
            "declared_capability": "",
            "declared_evidence": "declared" if capabilities else "not-declared",
            "enabled": enabled,
            "evidence_policy": str(policy),
        })
    return rows


def route_evidence(
    state: dict,
    *,
    stage: str,
    design_characterisation: Mapping,
    reference_adapters: Mapping | None = None,
    capture_adapters: Mapping | None = None,
    registries: Mapping | None = None,
    task_id: str = "",
    reason: str = "",
    evidence_policy: str = "declared",
) -> dict:
    """Route one design-evidence need to a declared adapter through the AR-202 rules.

    The decision is recorded in the same ``routing_decisions`` collection with the
    same vocabulary, because design intelligence must not bypass routing: an
    unavailable capability produces a ``blocked`` route, never a fabricated
    artifact or an assumed one.

    ``evidence_policy`` is the explicit capability-evidence policy:

    ``declared``  the historical behaviour: a declared capability suffices unless
                  the registry *observed* it unavailable
    ``observed``  requires at least AVAILABLE from a deterministic probe
    ``strict``    requires EXERCISED or VERIFIED with CURRENT freshness

    The policy is recorded on the decision, so a route can always be re-read with
    the standard it was decided under.
    """
    from . import capabilities as capability_module

    characteristics = design_characterisation.get("characteristics") or {}
    vocabulary = evidence_vocabulary_problems()
    if vocabulary:
        raise ContractError("design evidence routing vocabulary is inconsistent: " + "; ".join(vocabulary))
    if evidence_policy not in ("declared", "observed", "strict"):
        raise ContractError(f"unknown capability evidence policy: {evidence_policy!r}")
    needs = design_evidence_needs(characteristics)
    families: dict[str, Mapping] = {
        "reference": reference_adapters or {},
        "capture": capture_adapters or {},
        "registry": registries or {},
    }
    decision = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "decision_id": contracts.new_record_id("rte"),
        "run_id": str(state.get("run_id", "")),
        "stage": str(stage),
        "task_id": str(task_id or design_characterisation.get("task_id", "")),
        "characterisation_id": str(design_characterisation.get("characterisation_id", "")),
        "kind": "design-evidence",
        "required_capabilities": sorted({str(item["capability"]) for item in needs}),
        "candidates": [],
        "exclusions": [],
        "chosen": {},
        "fallbacks": [],
        "status": "selected",
        "rule": "capability-required",
        "reason": reason or "design evidence needs are satisfied by declared adapters",
        "policy_version": contracts.POLICY_VERSION,
        "evidence_policy": str(evidence_policy),
        "requested": {"provider": "", "model": "", "effort": "", "worker_role": ""},
        "prior_attempts": [],
        "failure_evidence": {},
        "strategy_change_required": False,
        "identity_pinned": False,
        "needs": [],
        "optional_needs": [],
        "recorded_at": contracts.utc_now(),
    }
    missing: list[str] = []
    for need in needs:
        family, capability = EVIDENCE_CAPABILITY_SOURCES[need["capability"]]
        candidates = _adapter_candidates(
            families.get(family) or {}, family, state=state, policy=evidence_policy,
        )
        sufficient: list[str] = []
        for candidate in candidates:
            capability_ids = {str(item["id"]) for item in candidate["capabilities"]}
            exclusions: list[str] = []
            if capability not in capability_ids:
                exclusions.append(f"missing required capability: {capability}")
            if not candidate.get("enabled", True):
                exclusions.append("the adapter is not configured or not authorized here")
            evidence = (candidate.get("capability_evidence") or {}).get(capability) if capability in capability_ids else None
            if evidence is not None:
                ok, evidence_reason = capability_module.satisfies(
                    str(evidence.get("status", "UNKNOWN")),
                    str(evidence.get("freshness", "UNKNOWN")),
                    policy=evidence_policy,
                )
                if not ok:
                    exclusions.append(f"capability evidence does not satisfy policy {evidence_policy!r}: {evidence_reason}")
            candidate["satisfies"] = not exclusions
            candidate["exclusions"] = exclusions
            decision["candidates"].append({
                "id": candidate["id"], "kind": family, "capability": capability,
                "satisfies": candidate["satisfies"], "exclusions": exclusions,
                "capability_evidence": dict(evidence or {}),
                "evidence_policy": str(evidence_policy),
            })
            if exclusions:
                decision["exclusions"].append({"id": candidate["id"], "reasons": exclusions})
            else:
                sufficient.append(str(candidate["id"]))
        entry = {
            "need": need["need"],
            "capability": need["capability"],
            "characteristic": need["characteristic"],
            "family": family,
            "sufficient": sufficient,
            "status": "satisfied" if sufficient else "unavailable",
        }
        decision["needs"].append(entry)
        if not sufficient:
            missing.append(f"{need['need']} needs {capability} and no {family} adapter satisfies it")
    for need in design_evidence_needs(characteristics, optional=True):
        family, capability = EVIDENCE_CAPABILITY_SOURCES[need["capability"]]
        available = [
            str(candidate["id"]) for candidate in _adapter_candidates(families.get(family) or {}, family)
            if capability in {str(item["id"]) for item in candidate["capabilities"]}
            and candidate.get("enabled", True)
        ]
        decision["optional_needs"].append({
            "need": need["need"],
            "capability": need["capability"],
            "family": family,
            "available": available,
            "status": "available" if available else "not-available",
            "note": "an opportunity, not an obligation: its absence never blocks the route",
        })
    if missing:
        decision["status"] = "blocked"
        decision["rule"] = "design-evidence-unavailable"
        decision["reason"] = (
            "the design task requires evidence no declared adapter can produce: " + "; ".join(missing)
        )
        _ensure_candidate(decision)
        return decision
    if not needs:
        decision["status"] = "selected"
        decision["rule"] = "sufficient-capability"
        decision["reason"] = reason or "this task requires no design evidence capability"
        decision["chosen"] = {"id": "none-required", "kind": "design-evidence", "capability_verdict": "sufficient"}
        _ensure_candidate(decision)
        return decision
    chosen_ids = sorted({str(item) for entry in decision["needs"] for item in entry["sufficient"]})
    decision["chosen"] = {
        "id": chosen_ids[0] if len(chosen_ids) == 1 else "multiple",
        "kind": "design-evidence",
        "capability_verdict": "sufficient",
        "adapters": chosen_ids,
    }
    _ensure_candidate(decision)
    return decision

def _ensure_candidate(decision: dict) -> None:
    """Keep the routing record structurally valid: it always names what it considered.

    When a task needs no evidence capability, the route records that fact as the
    candidate it considered, so the decision is still auditable.
    """
    if decision.get("candidates"):
        return
    decision["candidates"].append({
        "id": "none-required",
        "kind": "design-evidence",
        "capability": "",
        "satisfies": True,
        "exclusions": [],
    })


def stage_requirements(stage: str, characterisation: Mapping) -> list[dict]:
    """The required capabilities for a boundary, derived from the stage itself.

    Deriving them here as well as in ``characterize`` keeps a routing decision
    coherent even if a caller passes a characterisation produced for another
    boundary: a reasoning stage never demands implementation capabilities and an
    implementation boundary always demands implementation capability.
    """
    declared = [dict(item) for item in (characterisation.get("required_capabilities") or [])]
    if stage == "S4B":
        required = [item for item in declared if str(item.get("id")) in WORKER_CAPABILITY_IDS]
        if "implementation" not in {str(item.get("id")) for item in required}:
            required.insert(0, {
                "id": "implementation", "source": "rule-derived",
                "evidence": "stage S4B implements a bounded handoff",
            })
        return required
    capability = REASONING_STAGE_CAPABILITY.get(stage)
    required = [item for item in declared if str(item.get("id")) not in WORKER_CAPABILITY_IDS]
    if capability and capability not in {str(item.get("id")) for item in required}:
        required.append({
            "id": capability, "source": "rule-derived", "evidence": f"stage {stage} reasoning work",
        })
    return required

STRATEGY_CHANGE_CLASSES = ("TIMEOUT", "PROVIDER_FAILURE", "ENVIRONMENT_FAILURE", "CAPABILITY_FAILURE", "STALE_REVISION")
"""Failure classes that mean "do not simply repeat the same runtime"."""

NEVER_ROUTE_AROUND = ("AUTHORIZATION_FAILURE",)
"""Classes where routing must stop and a human must decide."""

HIGH_DIFFICULTY_TOKENS = (
    "architecture", "refactor", "migrate", "migration", "performance", "concurrency",
    "distributed", "rewrite", "schema change", "critical path", "security model",
)
MEDIUM_DIFFICULTY_TOKENS = (
    "integrate", "integration", "component", "responsive", "animation", "state management",
    "api", "authentication", "data model",
)
"""Declared request tokens that raise difficulty. They are evidence of *declared*
intent, not a measurement of the work. (Exported so a fixture can see the rule.)"""

HIGH_STAKES_TOKENS = (
    "production", "release", "customer", "payment", "checkout", "security", "privacy",
    "credentials", "secrets", "legal", "medical", "compliance", "live users",
)
"""Request tokens that raise stakes. See HIGH_DIFFICULTY_TOKENS for the caveat."""

SENSITIVE_SEGMENTS = (
    "auth", "login", "session", "password", "secret", "token", "credential", "payment",
    "billing", "checkout", "admin", "migration", ".env", "settings",
)
"""Sensitive subsystems (the transport's own sensitive-path vocabulary)."""

DIFFICULTY_ORDER = ("UNKNOWN", "LOW", "MEDIUM", "HIGH")
LEVEL_ORDER = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}

PLACEHOLDER_IDENTITY_TOKENS = (
    "default", "unverified", "not specified", "unknown", "n/a", "none", "not recorded", "<",
)
"""Declared model values that are placeholders, not a pinned identity.

"provider default – unverified" is a statement that the run did not pin a model.
Recording a requested/reported mismatch as a failure against a placeholder would
punish the honest case; only a concrete declared model is a pin the engine
enforces.
"""


def declared_identity_pin(state: dict, handoff_contract: Mapping | None = None) -> str:
    """The concrete model identity this run declared, or ``''`` when none is pinned."""
    preflight = state.get("provider_preflight") if isinstance(state.get("provider_preflight"), Mapping) else {}
    candidates = [str((preflight or {}).get("model", "") or "")]
    if isinstance(handoff_contract, Mapping):
        routing = handoff_contract.get("routing") if isinstance(handoff_contract.get("routing"), Mapping) else {}
        candidates.append(str((routing or {}).get("model", "") or ""))
    for value in candidates:
        text = value.strip()
        lowered = text.lower()
        if not text or any(token in lowered for token in PLACEHOLDER_IDENTITY_TOKENS):
            continue
        return text
    return ""


def _characteristic(value: str, source: str, evidence: tuple[str, ...]) -> dict:
    return {"value": value, "source": source, "evidence": [item for item in evidence if item]}


def _unknown(source: str = "not-observed") -> dict:
    return _characteristic("UNKNOWN", source, ())


def _request_tokens(request: str) -> list[str]:
    lowered = str(request or "").lower()
    return [token for token in HIGH_DIFFICULTY_TOKENS + MEDIUM_DIFFICULTY_TOKENS + HIGH_STAKES_TOKENS if token in lowered]


def _load_handoff_contract(project: Path, transport) -> dict:
    path = Path(project) / "HANDOFF.md"
    if not path.is_file():
        return {}
    try:
        return transport.worker_contract(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _sensitive_scope(scope_rows: list) -> list[str]:
    hits = []
    for row in scope_rows:
        text = " ".join(str(cell) for cell in row).lower()
        if any(segment in text for segment in SENSITIVE_SEGMENTS):
            hits.append(str(row[0]) if row else "")
    return [item for item in hits if item]


# ------------------------------------------------------------- characterisation

def characterize(
    state: dict,
    *,
    project: Path,
    stage: str,
    task_id: str = "",
    transport=None,
    creative=None,
    operations=None,
    request: str | None = None,
    dependencies: tuple[str, ...] = (),
) -> dict:
    """Derive the smallest useful, evidence-named task characterisation."""
    project = Path(project)
    text = str(request if request is not None else state.get("request", "") or "")
    tokens = _request_tokens(text)
    contract = _load_handoff_contract(project, transport) if transport is not None else {}
    scope_rows = list(contract.get("scope_rows") or [])
    validation_rows = list(contract.get("validation_rows") or [])
    declared_role = str(contract.get("worker_role") or "")

    executions = [item for item in (state.get("executions") or []) if isinstance(item, dict)]
    prior_task_failures = [
        item for item in (state.get("failures") or [])
        if isinstance(item, dict) and (not task_id or str(item.get("task_id", "")) == str(task_id))
    ]
    repair_attempts = 0
    worker = state.get("worker") or {}
    try:
        repair_attempts = int(worker.get("repair_attempts", 0) or 0)
    except (TypeError, ValueError):
        repair_attempts = 0

    # ---------------------------------------------------------- task type
    stage_types = {
        "S1": "brief", "S2": "research", "S3": "design-direction",
        "S4A": "implementation-planning", "S4B": "implementation",
        "S5": "review", "S6": "retrospective",
    }
    task_type = _characteristic(
        stage_types.get(stage, "unknown"), "rule-derived",
        (f"stage {stage} defines the boundary kind",),
    )

    # --------------------------------------------------------- difficulty
    difficulty_evidence: list[str] = []
    difficulty = "LOW"
    if len(prior_task_failures) >= 2 or repair_attempts >= 2:
        difficulty, difficulty_evidence = "HIGH", [
            f"{len(prior_task_failures)} recorded failure(s) for this task",
            f"{repair_attempts} routine repair attempt(s) already spent",
        ]
    elif prior_task_failures or repair_attempts:
        difficulty, difficulty_evidence = "MEDIUM", [
            f"{len(prior_task_failures)} recorded failure(s) for this task",
        ]
    if any(token in HIGH_DIFFICULTY_TOKENS for token in tokens):
        difficulty = "HIGH"
        difficulty_evidence.append("the request declares high-difficulty work: " + ", ".join(
            token for token in HIGH_DIFFICULTY_TOKENS if token in tokens
        ))
    elif any(token in MEDIUM_DIFFICULTY_TOKENS for token in tokens) and difficulty == "LOW":
        difficulty = "MEDIUM"
        difficulty_evidence.append("the request declares integration work: " + ", ".join(
            token for token in MEDIUM_DIFFICULTY_TOKENS if token in tokens
        ))
    if declared_role in ("strong", "senior-reasoning"):
        difficulty = "HIGH" if declared_role == "senior-reasoning" else max(difficulty, "MEDIUM", key=LEVEL_ORDER.get)
        difficulty_evidence.append(f"the handoff declares the {declared_role} worker role")
    # A wide permitted scope is a signal, not a measurement: only an unusually
    # broad contract moves difficulty, so a normal handoff is not inflated.
    if len(scope_rows) > 8:
        difficulty = "HIGH"
        difficulty_evidence.append(f"{len(scope_rows)} permitted scope rows")
    elif len(scope_rows) > 5 and LEVEL_ORDER[difficulty] < LEVEL_ORDER["MEDIUM"]:
        difficulty = "MEDIUM"
        difficulty_evidence.append(f"{len(scope_rows)} permitted scope rows")
    if not tokens and not scope_rows and not prior_task_failures and not repair_attempts:
        difficulty, difficulty_evidence = "UNKNOWN", ()

    # ------------------------------------------------------------- stakes
    stakes_evidence: list[str] = []
    stakes = "LOW"
    sensitive = _sensitive_scope(scope_rows)
    if sensitive:
        stakes, stakes_evidence = "HIGH", [f"sensitive subsystem in permitted scope: {', '.join(sensitive)}"]
    hits = [token for token in HIGH_STAKES_TOKENS if token in tokens]
    if hits:
        stakes = "HIGH"
        stakes_evidence.append("the request declares high-stakes work: " + ", ".join(hits))
    if dependencies:
        stakes = "HIGH"
        stakes_evidence.append("the handoff declares dependencies that need authorization to install")
    if any(token in text.lower() for token in ("preview", "deploy", "ship")):
        if LEVEL_ORDER[stakes] < LEVEL_ORDER["MEDIUM"]:
            stakes = "MEDIUM"
            stakes_evidence.append("the request references an external target")
    if not sensitive and not hits and not dependencies and not text:
        stakes, stakes_evidence = "UNKNOWN", ()

    # ------------------------------------------------- required capabilities
    required: list[dict] = []
    if stage in REASONING_STAGE_CAPABILITY:
        required.append({
            "id": REASONING_STAGE_CAPABILITY[stage],
            "source": "rule-derived",
            "evidence": f"stage {stage} reasoning work",
        })
    if stage == "S4B":
        required.append({"id": "implementation", "source": "rule-derived", "evidence": "stage S4B implements a bounded handoff"})
        needs_repair = LEVEL_ORDER[difficulty] >= LEVEL_ORDER["MEDIUM"] or LEVEL_ORDER[stakes] >= LEVEL_ORDER["HIGH"]
        if needs_repair:
            required.append({
                "id": "implementation-repair",
                "source": "rule-derived",
                "evidence": f"difficulty {difficulty} / stakes {stakes} require a repair-capable worker",
            })
        if prior_task_failures:
            required.append({
                "id": "escalation",
                "source": "runtime-observed",
                "evidence": f"{len(prior_task_failures)} recorded failure(s) for this task",
            })

    # ------------------------------------------------------- change scope
    if scope_rows:
        expected = _characteristic(
            "multi-file" if len(scope_rows) > 3 else "bounded",
            "user-declared",
            (f"{len(scope_rows)} permitted scope rows in the handoff contract",),
        )
    else:
        expected = _unknown("no handoff contract in this boundary")

    subsystem = _characteristic(
        (sensitive[0] if sensitive else ("handoff-declared scope" if scope_rows else "unknown")),
        "rule-derived" if sensitive or scope_rows else "not-observed",
        tuple(stakes_evidence if sensitive else ()),
    )

    validation_needs = _characteristic(
        "HIGH" if len(validation_rows) > 4 else ("MEDIUM" if validation_rows else "UNKNOWN"),
        "user-declared" if validation_rows else "not-observed",
        (f"{len(validation_rows)} declared validation command(s)",) if validation_rows else (),
    )
    review_needs = _characteristic(
        "REQUIRED" if stage in ("S4B", "S5") else "STAGE-DEFAULT",
        "rule-derived",
        (f"stage {stage} produces reviewable evidence",),
    )
    context_sensitivity = _characteristic(
        "HIGH" if stage in ("S3", "S5") else ("MEDIUM" if stage in ("S2", "S4A") else "LOW"),
        "rule-derived",
        (f"stage {stage} delivers an isolated or creative context",),
    )
    uncertainty = _characteristic(
        "HIGH" if prior_task_failures else ("MEDIUM" if not scope_rows and stage == "S4B" else "LOW"),
        "runtime-observed" if prior_task_failures else "rule-derived",
        (f"{len(prior_task_failures)} recorded failure(s)",) if prior_task_failures else (),
    )

    preflight = state.get("provider_preflight") if isinstance(state.get("provider_preflight"), dict) else {}
    declared = {
        "provider": str(preflight.get("provider", "") or ""),
        "model": str(preflight.get("model", "") or ""),
        "effort": str(preflight.get("effort", "") or ""),
        "worker_role": declared_role,
    }
    record = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "characterisation_id": contracts.new_record_id("tsk"),
        "run_id": str(state.get("run_id", "")),
        "stage": str(stage),
        "task_id": str(task_id),
        "task_type": task_type,
        "difficulty": _characteristic(difficulty, "rule-derived" if difficulty_evidence else "not-observed", tuple(difficulty_evidence)),
        "stakes": _characteristic(stakes, "rule-derived" if stakes_evidence else "not-observed", tuple(stakes_evidence)),
        "required_capabilities": required,
        "expected_change_scope": expected,
        "subsystem": subsystem,
        "validation_needs": validation_needs,
        "review_needs": review_needs,
        "context_sensitivity": context_sensitivity,
        "uncertainty": uncertainty,
        "declared": declared,
        "prior_failures": [
            {"task_id": item.get("task_id"), "class": item.get("class"), "recorded_at": item.get("recorded_at")}
            for item in prior_task_failures[-5:]
        ],
        "policy_version": contracts.POLICY_VERSION,
        "recorded_at": contracts.utc_now(),
    }
    if record["prior_failures"]:
        record["difficulty"]["source"] = "runtime-observed"
        record["stakes"]["source"] = "runtime-observed" if not stakes_evidence else record["stakes"]["source"]
    return record


def characterisation_problems(record: Mapping) -> list[str]:
    problems = contracts.adaptive_schema_problems(record)
    if not isinstance(record, Mapping):
        return problems
    if not re.fullmatch(r"tsk_[0-9TZ]+_[0-9a-f]{8}", str(record.get("characterisation_id", ""))):
        problems.append("characterisation has a malformed id")
    for name in ("task_type", "difficulty", "stakes", "uncertainty"):
        value = record.get(name)
        if not isinstance(value, Mapping) or not str(value.get("value", "")).strip():
            problems.append(f"characterisation has no {name}")
        elif str(value.get("value")) == "UNKNOWN" and not isinstance(value, Mapping):
            problems.append(f"characterisation {name} is malformed")
    for name in ("difficulty", "stakes"):
        value = str((record.get(name) or {}).get("value", ""))
        if value not in ("LOW", "MEDIUM", "HIGH", "UNKNOWN"):
            problems.append(f"characterisation {name} is not an ordinal value: {value!r}")
    if not isinstance(record.get("required_capabilities"), list):
        problems.append("characterisation lists no required capabilities")
    return problems


# ------------------------------------------------------------------- routing

def _reasoner_candidates(contract: Mapping, capability: str) -> list[dict]:
    rows = []
    for provider_id, provider in sorted((contract.get("providers") or {}).items()):
        capabilities = dict(provider.get("capabilities") or {})
        evidence = str(capabilities.get(capability, "") or "")
        rows.append({
            "id": provider_id,
            "kind": "reasoner",
            "capabilities": {capability: evidence} if evidence else {},
            "declared_capability": capability,
            "declared_evidence": evidence or "not-declared",
            "entry": str(provider.get("entry", "")),
            "opt_in": bool(provider.get("opt_in")),
        })
    return rows


def _worker_candidates(required: list[dict]) -> list[dict]:
    required_ids = {str(item.get("id")) for item in required}
    rows = []
    for role, capabilities in WORKER_ROLE_CAPABILITIES.items():
        rows.append({
            "id": role,
            "kind": "worker-role",
            "capabilities": {item: "declared" for item in capabilities},
            "declared_capability": "declared",
            "declared_evidence": "declared",
            "satisfies": required_ids <= set(capabilities),
        })
    return rows


def _exclusion_reasons(candidate: Mapping, required: list[dict], *, selectable: bool | None) -> list[str]:
    reasons = []
    required_ids = {str(item.get("id")) for item in required}
    capable = set(str(item) for item in (candidate.get("capabilities") or {}))
    missing = sorted(required_ids - capable)
    if missing:
        reasons.append("missing required capability: " + ", ".join(missing))
    if selectable is False:
        reasons.append("the runtime is not selectable here (not detected or not authorized)")
    return reasons


def route(
    state: dict,
    *,
    stage: str,
    characterisation: Mapping,
    task_id: str = "",
    declared_role: str = "",
    escalate: bool = False,
    requested_role: str = "",
    reasoner_selection: Mapping | None = None,
    reasoner_contract: Mapping | None = None,
    reasoner_capability: Mapping | None = None,
    project: Path | None = None,
    reason: str = "",
) -> dict:
    """Choose the execution strategy for one boundary with explicit ordered rules."""
    required = stage_requirements(stage, characterisation)
    required_ids = {str(item.get("id")) for item in required}
    prior = [item for item in (state.get("failures") or []) if isinstance(item, dict)]
    last = prior[-1] if prior else {}
    last_class = str(last.get("class", ""))
    last_strategy = str(last.get("strategy", "") or "")
    strategy_change_required = last_class in STRATEGY_CHANGE_CLASSES

    decision = {
        "schema_version": contracts.SCHEMA_ADAPTIVE,
        "decision_id": contracts.new_record_id("rte"),
        "run_id": str(state.get("run_id", "")),
        "stage": str(stage),
        "task_id": str(task_id),
        "characterisation_id": str(characterisation.get("characterisation_id", "")),
        "required_capabilities": sorted(required_ids),
        "candidates": [],
        "exclusions": [],
        "chosen": {},
        "fallbacks": [],
        "status": "no-route",
        "rule": "no-authorized-candidate",
        "reason": reason or "no candidate satisfies the required capabilities",
        "policy_version": contracts.POLICY_VERSION,
        "requested": {"provider": "", "model": "", "effort": "", "worker_role": ""},
        "prior_attempts": [
            {"task_id": item.get("task_id"), "class": item.get("class"), "strategy": item.get("strategy", "")}
            for item in prior[-5:]
        ],
        "failure_evidence": {"class": last_class, "retry_allowed": last.get("retry_allowed"), "strategy_change_allowed": last.get("strategy_change_allowed")},
        "strategy_change_required": bool(strategy_change_required),
        "identity_pinned": bool(declared_identity_pin(state)),
        "recorded_at": contracts.utc_now(),
    }

    if last_class in NEVER_ROUTE_AROUND:
        decision["rule"] = "policy-excluded"
        decision["reason"] = (
            f"the last failure is {last_class}; routing never continues around an authorization refusal"
        )
        decision["status"] = "blocked"
        return decision

    if stage == "S4B":
        candidates = _worker_candidates(required)
        order = {role: index for index, role in enumerate(("bulk", "strong", "senior-reasoning"))}
        declared = str(declared_role or (characterisation.get("declared") or {}).get("worker_role", "") or "")
        for candidate in candidates:
            candidate["exclusions"] = _exclusion_reasons(candidate, required, selectable=True)
            decision["candidates"].append({
                "id": candidate["id"], "kind": candidate["kind"],
                "satisfies": candidate.get("satisfies", False),
                "exclusions": candidate["exclusions"],
            })
        sufficient = [candidate["id"] for candidate in candidates if not candidate["exclusions"]]
        decision["exclusions"] = [
            {"id": candidate["id"], "reasons": candidate["exclusions"]}
            for candidate in candidates if candidate["exclusions"]
        ]
        if escalate:
            base = declared or "bulk"
            if not declared and not requested_role:
                decision["status"] = "blocked"
                decision["rule"] = "policy-excluded"
                decision["reason"] = "escalation needs the recorded current worker role; none is recorded"
                return decision
            stronger = [
                role for role in sufficient
                if order.get(role, -1) > order.get(base, -1)
            ]
            if requested_role and requested_role not in sufficient:
                decision["status"] = "blocked"
                decision["rule"] = "capability-required" if requested_role in WORKER_ROLE_CAPABILITIES else "policy-excluded"
                decision["reason"] = (
                    f"the requested escalation role {requested_role!r} does not satisfy "
                    f"{sorted(required_ids) or ['implementation']} or is not a supported role"
                )
                return decision
            if requested_role and order.get(requested_role, -1) <= order.get(base, -1):
                decision["status"] = "blocked"
                decision["rule"] = "policy-excluded"
                decision["reason"] = f"escalation role {requested_role} is not stronger than {base}"
                return decision
            if requested_role:
                chosen = requested_role
                rule = "declared-default"
            elif stronger:
                # Prefer the lightest sufficient role that is stronger than the
                # current one, unless the failure evidence demands escalation.
                chosen = "senior-reasoning" if "escalation" in required_ids and "senior-reasoning" in stronger else stronger[0]
                rule = "escalation-required"
            else:
                decision["status"] = "no-route"
                decision["rule"] = "no-authorized-candidate"
                decision["reason"] = (
                    f"escalation was requested from {base!r} but no stronger role satisfies "
                    f"{sorted(required_ids) or ['implementation']}"
                )
                return decision
        else:
            chosen = requested_role or declared or "bulk"
            rule = "declared-default"
            if chosen not in WORKER_ROLE_CAPABILITIES:
                decision["status"] = "blocked"
                decision["rule"] = "policy-excluded"
                decision["reason"] = f"unsupported worker role: {chosen}"
                return decision
        capable = set(WORKER_ROLE_CAPABILITIES.get(chosen, ()))
        missing = sorted(required_ids - capable)
        verdict = "sufficient" if not missing else "insufficient"
        repeats_failed_strategy = bool(last_strategy) and last_strategy == chosen
        if strategy_change_required and (missing or repeats_failed_strategy):
            decision["status"] = "blocked"
            decision["rule"] = "repeat-failure-avoided"
            decision["reason"] = (
                f"the {last_class} failure for this task requires a different strategy, but {chosen!r} "
                + (f"is the strategy that failed" if repeats_failed_strategy else f"still misses {missing}")
            )
            decision["chosen"] = {"id": chosen, "kind": "worker-role", "capability_verdict": verdict}
            return decision
        decision["chosen"] = {
            "id": chosen,
            "kind": "worker-role",
            "capability_verdict": verdict,
            "missing_capabilities": missing,
            "adapter": "scripts/prepare-stage.py:worker",
        }
        decision["fallbacks"] = [
            {"id": role, "kind": "worker-role", "reason": "sufficient and stronger" if order[role] > order[chosen] else "sufficient"}
            for role in sufficient if role != chosen
        ]
        decision["status"] = "selected"
        decision["rule"] = rule
        decision["reason"] = reason or (
            f"{chosen!r} selected: {verdict} for {sorted(required_ids) or ['implementation']}"
        )
        decision["requested"] = {
            "provider": str((state.get("provider_preflight") or {}).get("provider", "") or ""),
            "model": str((state.get("provider_preflight") or {}).get("model", "") or ""),
            "effort": str((state.get("provider_preflight") or {}).get("effort", "") or ""),
            "worker_role": chosen,
        }
        return decision

    # ------------------------------------------------------- reasoning stages
    contract = dict(reasoner_contract or {})
    capability_id = REASONING_STAGE_CAPABILITY.get(stage)
    selection = dict(reasoner_selection or {"id": contract.get("default", "")})
    selected_id = str(selection.get("id", "") or contract.get("default", ""))
    candidates = _reasoner_candidates(contract, capability_id) if capability_id else []
    selectable = None
    if isinstance(reasoner_capability, Mapping):
        selectable = str(reasoner_capability.get("availability", "")) in ("embedded", "detected")
    sufficient: list[str] = []
    for candidate in candidates:
        exclusions = _exclusion_reasons(
            candidate, required,
            selectable=(selectable if candidate["id"] == selected_id else None),
        )
        decision["candidates"].append({
            "id": candidate["id"], "kind": candidate["kind"],
            "capability_evidence": candidate.get("declared_evidence", "not-declared"),
            "satisfies": not exclusions,
            "exclusions": exclusions,
        })
        if exclusions:
            decision["exclusions"].append({"id": candidate["id"], "reasons": exclusions})
        else:
            sufficient.append(str(candidate["id"]))
    if selected_id not in sufficient:
        decision["status"] = "no-route"
        decision["rule"] = "capability-required" if sufficient else "no-authorized-candidate"
        decision["reason"] = (
            f"the selected reasoner {selected_id!r} does not satisfy the required capability "
            f"{capability_id!r} with evidence; use select-reasoner to choose one of {sufficient or ['no candidate']}"
        )
        return decision
    if strategy_change_required and not decision["identity_pinned"]:
        alternate = [item for item in sufficient if item != selected_id]
        if alternate and last_class in ("TIMEOUT", "PROVIDER_FAILURE", "ENVIRONMENT_FAILURE"):
            decision["status"] = "fallback"
            decision["rule"] = "repeat-failure-avoided"
            decision["chosen"] = {"id": alternate[0], "kind": "reasoner", "adapter": "scripts/reasoners.py"}
            decision["fallbacks"] = [{"id": item, "kind": "reasoner", "reason": "capable"} for item in alternate[1:]]
            decision["reason"] = (
                f"the last failure was {last_class}; the same runtime is not repeated without a recorded decision"
            )
            decision["requested"] = {"provider": alternate[0], "model": "", "effort": "", "worker_role": ""}
            return decision
    decision["chosen"] = {
        "id": selected_id, "kind": "reasoner", "adapter": "scripts/reasoners.py",
        "capability_verdict": "sufficient",
    }
    decision["fallbacks"] = [
        {"id": item, "kind": "reasoner", "reason": "capable"} for item in sufficient if item != selected_id
    ]
    decision["status"] = "selected"
    decision["rule"] = "strategy-continuity"
    decision["reason"] = reason or (
        f"the recorded reasoner {selected_id!r} satisfies {capability_id!r}; selection continues until "
        "select-reasoner or record-reasoner-failure records a change"
    )
    decision["requested"] = {"provider": selected_id, "model": "", "effort": "", "worker_role": ""}
    return decision


def routing_problems(record: Mapping) -> list[str]:
    problems = contracts.routing_problems(record)
    return problems


def record(state: dict, decision: Mapping) -> dict:
    """Validate and append a routing decision to the run state."""
    problems = contracts.routing_problems(decision)
    if problems:
        raise ContractError("routing decision is malformed: " + "; ".join(problems))
    state.setdefault("routing_decisions", []).append(dict(decision))
    if len(state["routing_decisions"]) > 200:
        state["routing_decisions"] = state["routing_decisions"][-200:]
    return dict(decision)


def record_characterisation(state: dict, record_value: Mapping) -> dict:
    problems = characterisation_problems(record_value)
    if problems:
        raise ContractError("task characterisation is malformed: " + "; ".join(problems))
    state.setdefault("characterisations", []).append(dict(record_value))
    if len(state["characterisations"]) > 200:
        state["characterisations"] = state["characterisations"][-200:]
    return dict(record_value)


def latest(state: dict, name: str) -> dict:
    values = state.get(name)
    if isinstance(values, list) and values and isinstance(values[-1], dict):
        return values[-1]
    return {}


def describe(decision: Mapping) -> str:
    """A short operator sentence for one routing decision."""
    chosen = decision.get("chosen") or {}
    if decision.get("status") == "no-route" or decision.get("status") == "blocked":
        return f"no route: {decision.get('reason', 'no authorized candidate')}"
    return (
        f"{decision.get('status')} {chosen.get('id')} "
        f"({chosen.get('capability_verdict', 'unknown')}) by rule {decision.get('rule')}"
    )


def family_advice(
    state: dict,
    *,
    characterisation: Mapping | None = None,
    task_kind: str = "",
    provider=None,
    **options,
) -> dict:
    """The route family for a task, when its structure does not already resolve it.

    The advice is an input to routing, not a routing decision: the worker-role
    policy in :func:`route` remains deterministic and always wins, and a
    protected operation routes through human policy rather than a model.
    """
    derived = str(task_kind or "")
    if not derived and isinstance(characterisation, Mapping):
        value = characterisation.get("task_type")
        derived = str(value.get("value", "") if isinstance(value, Mapping) else value or "")
    from .decisions import integrations

    return integrations.route_family(
        state,
        task_kind=derived,
        provider=provider,
        **options,
    )


__all__ = [
    "REASONING_STAGE_CAPABILITY",
    "WORKER_ROLE_CAPABILITIES",
    "WORKER_CAPABILITY_IDS",
    "DESIGN_CAPABILITY_IDS",
    "EVIDENCE_CAPABILITY_SOURCES",
    "evidence_vocabulary_problems",
    "DESIGN_EVIDENCE_REQUIREMENTS",
    "DESIGN_OPTIONAL_EVIDENCE_NEEDS",
    "design_evidence_needs",
    "route_evidence",
    "STRATEGY_CHANGE_CLASSES",
    "NEVER_ROUTE_AROUND",
    "characterize",
    "characterisation_problems",
    "route",
    "record",
    "record_characterisation",
    "latest",
    "describe",
    "routing_problems",
    "family_advice",
]
