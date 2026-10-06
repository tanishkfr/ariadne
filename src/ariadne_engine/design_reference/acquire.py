"""Reference acquisition: search -> candidate -> fetch -> normalize -> register.

One orchestration, so the order of operations is the same wherever reference
research happens, and so each step's refusal is reported against the step that
caused it.

The order is the AR-220 acquisition order, and it is an order rather than a
preference because it encodes a priority:

1. the current project
2. an approved local DESIGN.md
3. a connected/available Figma or design source
4. approved component registries
5. curated design references (getdesign.md)
6. source repositories
7. broader live web inspection

:func:`acquire_references` stops as soon as the budget says stop, and reports
what it did *not* do. There is no "search until satisfied" loop: sufficiency is a
caller decision, because only the caller knows what would satisfy it.

Every registration goes through the AR-202D lifecycle, so a normalized reference
is a ``FOUND`` record carrying its classification, and reaching ``INSPECTED`` still
requires a real hashed evidence artifact under the existing rules. Normalisation
does not and cannot shortcut that.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from .. import contracts, references as references_module
from ..contracts import ContractError
from . import discovery, getdesign, normalize, safety, sets

ACQUISITION_ORDER = (
    "project", "local-design-file", "figma", "component-registry",
    "curated-analysis", "source-repository", "live-site",
)
"""Declared acquisition order. Higher priority is queried first and satisfies the
requirement soonest; the order exists so "which source did we ask" has a single
recorded answer."""


def _frozen_corpus() -> dict[str, bytes]:
    """The recorded getdesign.md documents shipped with this build.

    Offline acquisition serves these bytes and nothing else. A candidate the
    catalog knows but the recording does not contain is reported as skipped
    rather than fetched, which is what makes an offline run reproducible.
    """
    from . import FIXTURE_ROOT

    adapter = getdesign.GetDesignAdapter.from_corpus(FIXTURE_ROOT)
    return dict(adapter.corpus)


class AcquisitionOutcome(dict):
    """A plain dict subclass so the record serialises with no custom encoder."""

    @property
    def ok(self) -> bool:
        return bool(self.get("normalized", 0))


def acquire_references(
    state: dict,
    *,
    project: Path,
    query: str = "",
    requirement_scope: str = "",
    task_id: str = "",
    retrieved_at: str = "",
    retrieved_at_value: str = "",
    allow_external: bool = True,
    project_sufficient: bool = False,
    counter_query: str = "",
    budget: Mapping | None = None,
    live_fetch: object = None,
    catalog_entries: Sequence[Mapping] = (),
    max_references: int | None = None,
) -> AcquisitionOutcome:
    """Acquire and register design references, recording every step and refusal.

    Offline by default. ``live_fetch`` must be an operator-supplied authorized
    fetch capability; without one, only local and frozen-fixture references are
    acquired, and the outcome says so rather than pretending the network was
    consulted.

    ``project_sufficient`` is the *same* input
    :func:`discovery.external_reference_worthwhile` takes, and it is a parameter
    rather than a re-decision on purpose. An earlier version re-derived the
    justification internally, which meant a caller that had already established
    that the requirement reaches beyond the project's own evidence could be
    silently overridden by a second, stricter guess - the slice judged ``YES``
    and the acquisition reported ``NO`` with no explanation of the disagreement.

    ``counter_query`` runs a second search. A direction needs evidence about what
    it must not become as well as what it should emulate, and looking for the
    anti-pattern is a search like any other.
    """
    stamp = str(retrieved_at or retrieved_at_value or contracts.utc_now())
    resolved_budget = sets.resolve_budget(budget)
    # The AR-202D lifecycle re-hashes every local source against
    # ``contracts.permitted_project_root``, which refuses a state that names no
    # project. Recording the root here is what lets a local DESIGN.md be
    # re-verified later instead of being trusted on assertion.
    if not str(state.get("project", "") or ""):
        state["project"] = str(Path(project).resolve())
    elif Path(str(state["project"])).resolve() != Path(project).resolve():
        raise ContractError(
            f"this run's project is {state['project']!r} but acquisition was given {str(project)!r}; "
            "reference evidence is bound to one project and cannot be re-pointed at another"
        )
    resolved_budget = sets.resolve_budget(budget)
    outcome = AcquisitionOutcome({
        "query": str(query),
        "requirement_scope": str(requirement_scope),
        "order": list(ACQUISITION_ORDER),
        "steps": [],
        "candidates": [],
        "normalized": 0,
        "rejected": 0,
        "registered": [],
        "bytes_retrieved": 0,
        "budget": resolved_budget,
        "external_capability": "UNAVAILABLE",
        "external_reason": "",
        "injection": {},
        "started_at": stamp,
        "stopped_because": "",
    })

    def step(name: str, *, status: str, detail: str, **extra) -> None:
        outcome["steps"].append({"step": name, "status": status, "detail": detail, **extra})

    # -- 1. project-local evidence, before anything external -----------------
    local = discovery.discover(project)
    outcome["discovery"] = local
    step(
        "project", status="OK",
        detail=(
            "design documents: {docs}; css variables: {vars}; component files: {components}; "
            "figma links: {figma}"
        ).format(
            docs=len(local["probes"]["design_documents"]),
            vars=local["probes"]["design_tokens"]["css_variable_count"],
            components=local["probes"]["component_library"]["component_files"],
            figma=len(local["probes"]["figma_links"]["urls"]),
        ),
    )
    for row in discovery.local_reference_records(local, project=project):
        recorded = _register_local_design_file(state, row, project=project, task_id=task_id, stamp=stamp)
        if recorded is not None:
            outcome["registered"].append(recorded)
            outcome["normalized"] += 1

    value = discovery.external_reference_worthwhile(local, project_sufficient=project_sufficient)
    step("external-justification", status=value["verdict"], detail=str(value["reason"]))

    if not allow_external or value["verdict"] != "YES":
        outcome["stopped_because"] = (
            "external reference acquisition was not justified yet; project-local evidence is "
            "examined first and a design workflow must not depend on a network source"
        )
        outcome["injection"] = safety.instruction_attempt_summary([])
        return outcome

    # -- 5. curated analysis (getdesign.md) ----------------------------------
    entries = list(catalog_entries) or [row.as_record() for row in getdesign.default_adapter().candidates()]
    adapter = getdesign.default_adapter()
    adapter.index = [dict(row) for row in entries]
    adapter.corpus = _frozen_corpus()
    if live_fetch is not None:
        adapter.fetcher = live_fetch  # type: ignore[assignment]
    if not adapter.enabled() and not entries:
        outcome["external_capability"] = "UNAVAILABLE"
        outcome["external_reason"] = adapter.unavailable_reason()
        step("curated-analysis", status="UNAVAILABLE", detail=outcome["external_reason"])
        outcome["injection"] = safety.instruction_attempt_summary([])
        return outcome
    outcome["external_capability"] = "AVAILABLE" if adapter.enabled() else "UNAVAILABLE"
    outcome["external_reason"] = adapter.unavailable_reason()

    queries = [(str(query), False)]
    if counter_query:
        queries.append((str(counter_query), True))
    candidates: list[dict] = []
    counter_candidates: list[dict] = []
    for text, is_counter in queries:
        found = [row.as_record() for row in adapter.discover({"query": text})]
        # `candidate_retrieval` is a *cumulative* line, so each search spends
        # against it separately. Spending once at the end would let the first
        # search quietly consume the whole budget before the counter-reference
        # search ran, and the budget would only discover the overspend after the
        # retrieval it was supposed to bound.
        sets.spend(resolved_budget, "candidate_retrieval", len(found))
        if is_counter:
            counter_candidates.extend(found)
        else:
            candidates.extend(found)
    outcome["candidates"] = candidates
    outcome["counter_candidates"] = counter_candidates
    step(
        "search", status="OK",
        detail=f"{len(candidates)} candidate(s) for {query!r}"
        + (f"; {len(counter_candidates)} for the counter-query {counter_query!r}" if counter_query else ""),
        slugs=[row["slug"] for row in candidates],
        counter_slugs=[row["slug"] for row in counter_candidates],
        budget_after=sets.budget_verdict(resolved_budget),
    )

    cap = int(max_references or contracts.REFERENCE_BUDGET_DEFAULTS["deep_inspection"])
    # The two searches are inspected separately, on purpose. Ranking them together
    # lets a high-scoring entry from the anti-pattern search crowd out the primary
    # references, which inverts the request: the whole point of the counter search
    # is to find what to avoid, and letting it displace what to emulate means the
    # direction ends up built on the anti-pattern.
    primary_cap = max(int(cap) - int(contracts.REFERENCE_BUDGET_DEFAULTS["counter_references"]), 1)
    counter_cap = int(contracts.REFERENCE_BUDGET_DEFAULTS["counter_references"])

    def _select(rows: list[dict], limit: int) -> list[dict]:
        """Rank, then - offline - prefer what this build actually recorded, then cap.

        The order of those three steps matters. Prioritising *after* truncation
        cannot recover anything: with a counter-query cap of 2, ranking first
        returns the two highest-scoring entries, which offline may both be
        unrecorded, and the recording then yields nothing at all. The anti-pattern
        search would silently contribute no counter-reference and the direction
        would be built without one.
        """
        ranked = sets.rank_candidates(rows, limit=len(rows))
        if adapter.fetcher is None:
            ranked = sorted(
                ranked,
                key=lambda row: (
                    0 if str(row.get("slug", "")) in adapter.corpus else 1,
                    -float(row.get("score", 0.0) or 0.0),
                    str(row.get("slug", "")),
                ),
            )
        return ranked[: max(int(limit), 0)]

    plan = [
        (_select(candidates, primary_cap), False),
        (_select(counter_candidates, counter_cap), True),
    ]
    for selected_batch, from_counter_search in plan:
        for candidate in selected_batch:
            if adapter.fetcher is None and str(candidate.get("slug", "")) not in adapter.corpus:
                outcome["rejected"] += 1
                step(
                    "fetch", status="SKIPPED",
                    detail=(
                        f"{candidate['slug']} has no recorded document and no authorized fetch capability; "
                        "Ariadne does not invent reference content it has not retrieved"
                    ),
                    slug=candidate["slug"],
                    from_counter_search=from_counter_search,
                )
                continue
            try:
                sets.spend(resolved_budget, "deep_inspection")
                record = adapter.normalize(
                    getdesign.GetDesignCandidate(
                        slug=str(candidate["slug"]), brand=str(candidate.get("brand", "")),
                        summary=str(candidate.get("summary", "")),
                    ),
                    retrieved_at=stamp,
                )
            except ContractError as exc:
                outcome["rejected"] += 1
                step("fetch", status="REJECTED", detail=str(exc), slug=candidate["slug"])
                continue
            except Exception as exc:  # noqa: BLE001 - a dead transport must not kill the run
                # A connection error, a timeout, a DNS failure, a truncated body.
                # AR-220 requires the design workflow to continue from whatever
                # evidence it has rather than propagating a third party's outage
                # into the middle of a design task, so this is recorded and
                # counted rather than re-raised.
                outcome["rejected"] += 1
                step(
                    "fetch", status="REJECTED",
                    detail=(
                        f"{candidate['slug']} could not be retrieved: {type(exc).__name__}: {exc}. "
                        "Reference acquisition continues without it; no content was invented in its place"
                    ),
                    slug=candidate["slug"],
                )
                continue
            registered = _register_normalized(
                state, record, task_id=task_id, stamp=stamp, query=str(query),
                from_counter_search=from_counter_search,
            )
            outcome["registered"].append(registered)
            outcome["normalized"] += 1
            outcome["bytes_retrieved"] += int(record.get("retrieved_bytes", 0) or 0)

    outcome["budget"] = resolved_budget
    outcome["injection"] = safety.instruction_attempt_summary(
        [references_module.reference(state, row["reference_id"]) or {} for row in outcome["registered"]]
    )
    outcome["stopped_because"] = (
        "the reference budget was applied; Ariadne retrieved enough evidence to justify a direction "
        "and stopped rather than continuing to search"
    )
    return outcome


def _register_local_design_file(
    state: dict, row: Mapping, *, project: Path, task_id: str, stamp: str
) -> dict | None:
    """Register a project-local design document as a first-class reference.

    The project's own DESIGN.md is a real reference and is recorded as one - with
    ``source_kind = LOCAL_DESIGN_FILE``, which the preference order ranks above
    any curated analysis, because project identity is the primary constraint.
    """
    path = safety.contained_path(row["locator"], project, label="project design document")
    raw = path.read_bytes()
    relative = str(row.get("relative_path", path.name))
    record = references_module.register(
        state,
        source=f"project:{relative}",
        locator=str(path),
        title=str(row.get("title", path.name)),
        source_type="project-document",
        adapter="project-local-design",
        task_id=task_id,
        query=f"project design evidence for {relative}",
    )
    normalized = normalize.normalize_reference(
        source_kind="LOCAL_DESIGN_FILE",
        source_provider="project",
        source_identity=f"project:{relative}",
        source_uri=str(path),
        retrieved_at=stamp,
        content=raw,
        title=str(row.get("title", path.name)),
        reference_type="LOCAL_DESIGN_FILE",
        evidence_level="DIRECTLY_INSPECTED",
        access_mode="DECLARED_LOCAL",
        license_status="project-owned",
        attribution="the project's own design document",
    )
    normalized["design_document"]["bytes"] = len(raw)
    normalized["design_document"]["path"] = relative
    normalize.attach(record, normalized)
    references_module.mark_accessible(
        state, str(record["reference_id"]), content_sha256=str(row["sha256"]),
        size=len(raw), mime="text/markdown", retrieved_at=stamp,
        licence_note="project-owned design document", adapter="project-local-design",
    )
    return {
        "reference_id": str(record["reference_id"]),
        "source_kind": "LOCAL_DESIGN_FILE",
        "provider": "project",
        "identity": f"project:{relative}",
        "patterns": len(normalized["observed_patterns"]),
        "evidence_level": "DIRECTLY_INSPECTED",
    }


def _register_normalized(
    state: dict, normalized: Mapping, *, task_id: str, stamp: str, query: str,
    from_counter_search: bool = False,
) -> dict:
    """Register one normalized external reference into the existing lifecycle."""
    classification = normalized["classification"]
    candidate = normalized.get("candidate") if isinstance(normalized.get("candidate"), Mapping) else {}
    slug = str(candidate.get("slug", "")) or classification["source_identity"]
    title = str(normalized.get("title", "")) or slug
    record = references_module.register(
        state,
        source=f"{classification['source_provider']}:{slug}",
        locator=str(classification["source_uri"]),
        title=title,
        source_type="official-api",
        adapter="getdesign-md",
        task_id=task_id,
        query=str(query),
    )
    normalize.attach(record, normalized)
    references_module.mark_accessible(
        state, str(record["reference_id"]),
        content_sha256=str(classification["content_digest"]),
        size=int(normalized.get("design_document", {}).get("bytes", 0) or 0),
        mime="text/markdown",
        retrieved_at=stamp,
        licence_note=f"{normalized.get('license_status', '')}; {normalized.get('attribution', '')}",
        adapter="getdesign-md",
    )
    return {
        "reference_id": str(record["reference_id"]),
        "source_kind": str(classification["source_kind"]),
        "provider": str(classification["source_provider"]),
        "identity": str(classification["source_identity"]),
        "content_digest": str(classification["content_digest"]),
        "patterns": len(normalized["observed_patterns"]),
        "evidence_level": str(classification["evidence_level"]),
        "retrieved_bytes": int(normalized.get("design_document", {}).get("bytes", 0) or 0),
        "from_counter_search": bool(from_counter_search),
        "limitations": list(normalized.get("limitations") or []),
    }


def summary(outcome: Mapping) -> str:
    """A short operator view of one acquisition."""
    lines = [f"Reference acquisition: {outcome.get('query', '')!r}"]
    for step in outcome.get("steps") or []:
        lines.append(f"  [{step.get('status')}] {step.get('step')}: {step.get('detail')}")
    lines.append(
        f"  registered {outcome.get('normalized', 0)}, rejected {outcome.get('rejected', 0)}, "
        f"bytes {outcome.get('bytes_retrieved', 0)}"
    )
    lines.append(f"  budget: {(outcome.get('budget') or {}).get('verdict', 'UNKNOWN')}")
    if outcome.get("stopped_because"):
        lines.append(f"  stopped: {outcome['stopped_because']}")
    return "\n".join(lines)


__all__ = [
    "ACQUISITION_ORDER",
    "AcquisitionOutcome",
    "acquire_references",
    "summary",
]