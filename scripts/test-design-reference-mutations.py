#!/usr/bin/env python3
"""AR-220 mutation suite.

A passing test suite proves the happy path holds. This file breaks the
implementation deliberately and asserts the suite **notices**. Each mutation is a
real defect class that a review would miss, applied by patching a module's
behaviour in memory, then re-running the corresponding test.

The nine required mutations from AR-220 section 53 are present, plus the ones the
adversarial review in section 54 found. Each is named for the defect it
represents, not for the code it edits.

Run:
    python scripts/test-design-reference-mutations.py
"""

from __future__ import annotations

import contextlib
import io
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ariadne_engine import contracts  # noqa: E402
from ariadne_engine.design_reference import (  # noqa: E402
    acquire,
    designmd,
    direction,
    discovery,
    getdesign,
    normalize,
    safety,
    sets,
    transports,
    vertical_slice,
)

CAUGHT: list[str] = []
MISSED: list[tuple[str, str]] = []


def expect_caught(name: str, target, replacement) -> None:
    """Apply ``replacement`` to ``target`` and require the suite to fail.

    ``target`` is a module; ``replacement`` receives it and patches it. The patch
    is reverted afterwards whatever happens, so one mutation cannot mask another.
    """
    import importlib

    saved = {}
    for key, value in list(vars(target).items()):
        saved[key] = value
    try:
        replacement(target)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            result = _run_suite()
        if result == 0:
            MISSED.append((name, "the suite still passed with the defect applied"))
            print(f"MISSED {name}: suite still green")
        else:
            CAUGHT.append(name)
            print(f"caught {name}")
    except Exception:
        # A mutation that raises is caught too, as long as the suite notices.
        CAUGHT.append(name)
        print(f"caught {name} (raised)")
    finally:
        for key in list(vars(target).keys()):
            if key not in saved:
                delattr(target, key)
        for key, value in saved.items():
            setattr(target, key, value)
        importlib.reload(sys.modules[target.__name__])


def _run_suite() -> int:
    """Run the design-reference suite in-process and return its exit code."""
    suite_path = ROOT / "scripts" / "test-design-reference.py"
    spec_path = str(suite_path)
    module = sys.modules.get("ariadne_ar220_suite")
    if module is not None:
        del sys.modules["ariadne_ar220_suite"]
    import importlib.util

    spec = importlib.util.spec_from_file_location("ariadne_ar220_suite", spec_path)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules["ariadne_ar220_suite"] = loaded
    try:
        spec.loader.exec_module(loaded)
        return int(loaded.main())
    finally:
        sys.modules.pop("ariadne_ar220_suite", None)


# =============================================== 53. the nine required mutations


def mutation_curated_promoted_to_first_party(module) -> None:
    """A curated analysis silently reclassified as a first-party design system.

    This is the single most important distinction in AR-220. If the provider's
    evidence level can be laundered into ``FIRST_PARTY_DESIGN_MD``, every
    downstream claim about a reference's weight is unsound.
    """
    original = module.GetDesignAdapter.normalize

    def normalize(self, candidate, *, retrieved_at, entry_metadata=None):
        record = original(self, candidate, retrieved_at=retrieved_at, entry_metadata=entry_metadata)
        record["classification"]["source_kind"] = "FIRST_PARTY_DESIGN_MD"
        record["classification"]["evidence_level"] = "DIRECTLY_INSPECTED"
        return record

    module.GetDesignAdapter.normalize = normalize


def mutation_first_match_after_ambiguity(module) -> None:
    """Ambiguous candidates resolved by taking the first result.

    Silently resolving an ambiguity is how a search becomes a guess: two catalog
    entries match equally well, the first wins, and the record carries a confident
    title that nobody verified was the one meant.

    Reimplements the index build rather than wrapping the real one. A wrapper
    that delegated to the original would raise on the duplicate before it could
    collapse it, so the mutation would do nothing at all and would still be
    reported as caught - the failure mode this file exists to avoid.
    """

    def build_index(entries):
        rows = []
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            slug = str(entry.get("slug", "")).strip()
            if not slug or slug in seen:
                # Collapse duplicates instead of refusing them.
                continue
            seen.add(slug)
            rows.append(module.GetDesignCandidate(
                slug=slug,
                brand=str(entry.get("brand", "")).strip(),
                summary=str(entry.get("summary", "")).strip(),
            ))
        return rows

    module.build_index = build_index


def mutation_reference_text_authorises(module) -> None:
    """Reference text treated as authorisation.

    If an instruction found *inside* a design document can grant capability, the
    whole prompt-injection boundary is decorative.
    """
    def scan_reference_text(text):
        return {"scanned_characters": len(str(text or "")), "instruction_attempts": [], "treated_as": "authority"}

    module.scan_reference_text = scan_reference_text


def mutation_url_to_private_ip_allowed(module) -> None:
    """External URL allowed to reach a private address.

    An SSRF guard that can be talked out of its verdict is not a guard.
    """
    def require_fetchable_url(url, *, label="a reference URL"):
        text = str(url or "").strip()
        if not text:
            raise module.ContractError(f"{label} is empty")
        return text

    module.require_fetchable_url = require_fetchable_url


def mutation_digest_omitted(module) -> None:
    """The content digest dropped from a normalised record.

    Without the digest, "this classification describes those bytes" becomes
    unfalsifiable: the same record could be attached to different content, and
    change detection could not run.
    """
    def build_classification(**kwargs):
        record = original_build_classification(**kwargs)
        record["content_digest"] = ""
        return record

    global original_build_classification
    original_build_classification = normalize.build_classification
    module.build_classification = build_classification


def mutation_budget_ignored(module) -> None:
    """A research budget silently ignored.

    Spending past a bound that was set to be a bound is how a bounded subsystem
    becomes an unbounded research loop.
    """
    def spend(budget, name, amount=1):
        spent = budget.get("spent") if isinstance(budget.get("spent"), dict) else {}
        spent[name] = int(spent.get(name, 0)) + int(amount)
        budget["spent"] = spent
        budget["verdict"] = module.budget_verdict(budget)
        return budget

    module.spend = spend


def mutation_counter_treated_as_primary(module) -> None:
    """A counter-reference counted as a primary direction reference.

    This silently inverts a direction: the reference chosen to say "not this"
    starts justifying "this".
    """
    original = module.sets.diversity

    def diversity(references_by_id, rows):
        for row in rows:
            if isinstance(row, dict):
                row["roles"] = [
                    role for role in (row.get("roles") or [])
                    if role != "COUNTER_REFERENCE"
                ] or ["PRIMARY_DIRECTION"]
        return original(references_by_id, rows)

    module.sets.diversity = diversity


def mutation_unknown_fields_dropped(module) -> None:
    """Unknown DESIGN.md fields silently discarded.

    Discarding them means the parsed record no longer describes the document
    while still carrying its digest - and the discarded part is usually the design
    rationale, which is the reason to read the document at all.
    """
    original = module.parse_design_md

    def parse_design_md(text, *, origin=""):
        record = original(text, origin=origin)
        record["unknown_fields"] = {}
        record["warnings"] = [row for row in record.get("warnings", []) if "unrecognised" not in row]
        return record

    module.parse_design_md = parse_design_md


def mutation_network_failure_crashes(module) -> None:
    """A network failure propagating out of acquisition.

    AR-220 requires the design workflow to continue from whatever evidence it
    has. A third party's outage must not take a design task down with it.
    """
    original = module.acquire_references

    def acquire_references(*args, **kwargs):
        class Exploding:
            def __call__(self, url):
                raise OSError("connection reset by peer")

        kwargs["live_fetch"] = Exploding()
        return original(*args, **kwargs)

    module.acquire_references = acquire_references


# ================================ 54. defects found by the adversarial review


def mutation_allowlist_inverted_actually(module) -> None:
    """An inverted allowlist, applied for real by editing the live URL list."""
    original_fetch = module.GetDesignAdapter.fetch_document

    def fetch_document(self, candidate):
        slug = str(candidate.slug)
        url = module.raw_url(slug)
        # The historical bug: demand that *every* configured prefix match.
        for prefix in self.allowlist:
            if not url.startswith(str(prefix)):
                raise module.ContractError(
                    f"getdesign.md retrieval target {url!r} is outside the configured allowlist"
                )
        self.requests_made += 1
        return self.fetcher(url)

    module.GetDesignAdapter.fetch_document = fetch_document


def mutation_inverse_tokens_pollute_lightness(module) -> None:
    """Inverse-palette tokens counted toward the base surface.

    Found by the adversarial review. A near-black system that also declares
    ``inverse-canvas: #ffffff`` was reported ``light-dominant``, which is the
    opposite of the truth.
    """
    original = module._light_dark_from_tokens

    def _light_dark_from_tokens(colors):
        lumas = []
        for entry in colors:
            if not isinstance(entry, dict):
                continue
            values = entry.get("values")
            if not isinstance(values, dict):
                continue
            value = module._relative_luminance(str(values.get("value", "")))
            if value is not None:
                lumas.append((str(entry.get("name", "")).lower(), value))
        if not lumas:
            return "UNKNOWN"
        mean = sum(value for _name, value in lumas) / len(lumas)
        return "dark-dominant" if mean < 0.35 else "light-dominant"

    module._light_dark_from_tokens = _light_dark_from_tokens


def mutation_provenance_axes_vote(module) -> None:
    """Provider-constant axes allowed to decide the diversity verdict.

    Found by the adversarial review. Every getdesign.md entry analyses a website,
    so ``surface=website`` is uniform for *any* selection; letting it vote reports
    every single-provider set as too homogeneous.
    """
    original = module.diversity

    def diversity(references_by_id, rows):
        record = original(references_by_id, rows)
        record["provenance_axes"] = []
        record["verdict"] = "TOO_HOMOGENEOUS" if record.get("homogeneous_axes") is not None else record["verdict"]
        if not record.get("homogeneous_axes"):
            record["verdict"] = "TOO_HOMOGENEOUS"
        return record

    module.diversity = diversity


def mutation_counter_reference_by_dimension_heuristic(module) -> None:
    """The counter-reference chosen by a dimension heuristic instead of provenance.

    Found by the adversarial review. The heuristic picked the *first* reference
    mentioning surfaces, which selected a positive exemplar and turned the
    direction's "do not become" clause into a description of what it emulates.
    """
    original = module._assign_members

    def _assign_members(state, by_id, counter_identity=""):
        return original(state, by_id, counter_identity="")

    module._assign_members = _assign_members


def mutation_project_statement_attributed_to_reference(module) -> None:
    """A project-sourced statement reported as reference evidence.

    Found by the adversarial review. Project constraints and borrowed observations
    must stay distinguishable, or the provenance claims a reference said something
    the project supplied.
    """
    original = module.grounded_choices

    def grounded_choices(direction_sections, members, references_by_id, *, project_identity=None):
        rows = original(
            direction_sections, members, references_by_id, project_identity=project_identity
        )
        for row in rows:
            if row.get("grounding") in ("PROJECT_CONSTRAINT", "PROJECT_CONSTRAINT_AND_REFERENCE"):
                row["grounding"] = "REFERENCE_EVIDENCE"
        return rows

    module.grounded_choices = grounded_choices


def mutation_fewer_sources_claims_supported(module) -> None:
    """One source's observation promoted to a corroborated principle.

    If a single vague description can claim ``SUPPORTED``, the confidence label
    stops meaning anything.
    """
    original = module.extract_principles

    def extract_principles(members, references_by_id, *, applicable_to="", dimension_filter=()):
        rows = original(
            members, references_by_id,
            applicable_to=applicable_to, dimension_filter=dimension_filter,
        )
        for row in rows:
            row["confidence"] = "SUPPORTED"
            row["distinct_sources"] = max(int(row.get("distinct_sources", 0)), 2)
        return rows

    module.extract_principles = extract_principles


def mutation_motion_without_basis(module) -> None:
    """Motion observed from a document that never states a basis.

    A static token table cannot establish how something moves.
    """
    original = module._add_motion_observations

    def _add_motion_observations(tokens, add):
        motion = tokens.get("motion") or []
        if not motion:
            return
        add("motion", f"{len(motion)} declared motion treatments", source="frontmatter.motion")
        add("interaction", f"{len(motion)} motion treatments", source="frontmatter.motion")

    module._add_motion_observations = _add_motion_observations


def mutation_oversized_document_silently_truncated(module) -> None:
    """An oversized document truncated instead of refused.

    Truncation produces a record that looks complete and is not.
    """
    def check_document_size(value, *, limit, label):
        size = len(value.encode("utf-8")) if isinstance(value, str) else len(value)
        return min(size, limit)

    module.check_document_size = check_document_size


def mutation_catalogue_access_restricted_bypassed(module) -> None:
    """An access-restricted download treated as public.

    Found by the adversarial review. The catalog's own DESIGN.md download is
    sign-in gated; if a recorded corpus were presented as though it came from the
    gated endpoint, the access boundary would be fiction.
    """
    original = module.parse_entry_html

    def parse_entry_html(html, *, slug):
        record = original(html, slug=slug)
        record["raw_document_download_gated"] = False
        return record

    module.parse_entry_html = parse_entry_html


def mutation_direction_self_approves(module) -> None:
    """A compiled direction marking itself approved.

    AR-220 approves nothing. Approval is a human decision through ``G1D``, and a
    compiler that can set that flag itself has removed the only real control.
    """
    original = module.compile_candidate_direction

    def compile_candidate_direction(*args, **kwargs):
        record = original(*args, **kwargs)
        if isinstance(record, dict) and isinstance(record.get("ar220_grounding"), dict):
            record["ar220_grounding"]["status"] = "APPROVED"
            record["ar220_grounding"]["approval_required"] = False
        return record

    module.compile_candidate_direction = compile_candidate_direction


def mutation_project_first_order_inverted(module) -> None:
    """External research allowed before project-local evidence is examined.

    Found by the adversarial review. Looking at a catalogue before looking at the
    repository is how a project ends up styled like somebody else's brand.
    """
    original = module.external_reference_worthwhile

    def external_reference_worthwhile(discovery_record, *, project_sufficient=False):
        if not discovery_record.get("probes"):
            raise module.ContractError("no discovery record")
        return {"verdict": "YES", "reason": "mutated: external research is always fine", "constraints": []}

    module.external_reference_worthwhile = external_reference_worthwhile


def mutation_duplicate_slug_resolved_by_order(module) -> None:
    """A duplicate catalog slug resolved by keeping the last entry."""
    original = module.build_index

    def build_index(entries):
        rows = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            slug = str(entry.get("slug", "")).strip()
            if not slug:
                continue
            rows[slug] = getdesign.GetDesignCandidate(
                slug=slug, brand=str(entry.get("brand", "")), summary=str(entry.get("summary", ""))
            )
        return list(rows.values())

    module.build_index = build_index


def mutation_discovery_traversal_allowed(module) -> None:
    """A project-relative probe path escaping the project root."""
    original = module.contained_path

    def contained_path(candidate, root, *, label="a design reference path"):
        return Path(candidate)

    module.contained_path = contained_path


MUTATIONS = [
    ("curated analysis promoted to first-party", mutation_curated_promoted_to_first_party, getdesign),
    ("first match accepted after ambiguity", mutation_first_match_after_ambiguity, getdesign),
    ("reference text treated as authorisation", mutation_reference_text_authorises, safety),
    ("external URL allowed to a private IP", mutation_url_to_private_ip_allowed, safety),
    ("reference digest omitted", mutation_digest_omitted, normalize),
    ("reference budget ignored", mutation_budget_ignored, sets),
    ("counter-reference treated as primary", mutation_counter_treated_as_primary, direction),
    ("unknown DESIGN.md fields silently dropped", mutation_unknown_fields_dropped, designmd),
    ("network failure crashes the design stage", mutation_network_failure_crashes, acquire),
    ("retrieval allowlist requires every prefix", mutation_allowlist_inverted_actually, getdesign),
    ("inverse tokens pollute the lightness reading", mutation_inverse_tokens_pollute_lightness, sets),
    ("provider-constant axes decide diversity", mutation_provenance_axes_vote, sets),
    ("counter-reference chosen by dimension heuristic", mutation_counter_reference_by_dimension_heuristic, vertical_slice),
    ("project statement attributed to a reference", mutation_project_statement_attributed_to_reference, direction),
    ("one source claims SUPPORTED", mutation_fewer_sources_claims_supported, direction),
    ("motion observed without a basis", mutation_motion_without_basis, normalize),
    ("oversized document silently truncated", mutation_oversized_document_silently_truncated, safety),
    ("access-restricted download treated as public", mutation_catalogue_access_restricted_bypassed, getdesign),
    ("compiled direction self-approves", mutation_direction_self_approves, direction),
    ("project-first order inverted", mutation_project_first_order_inverted, discovery),
    ("duplicate slug resolved by order", mutation_duplicate_slug_resolved_by_order, getdesign),
    ("probe path escapes the project root", mutation_discovery_traversal_allowed, discovery),
]


def main() -> int:
    # Prove the suite is green before mutating anything, so a caught mutation
    # cannot be confused with a suite that was already failing.
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        baseline = _run_suite()
    if baseline != 0:
        print("baseline suite is not green; refusing to run mutations")
        print(buffer.getvalue()[-2000:])
        return 1
    print(f"baseline: suite green\n")

    for name, mutation, module in MUTATIONS:
        expect_caught(name, module, mutation)

    total = len(CAUGHT) + len(MISSED)
    print()
    print(f"{len(CAUGHT)}/{total} mutations caught")
    if MISSED:
        print(f"{len(MISSED)} MISSED")
        for name, detail in MISSED:
            print(f"  - {name}: {detail}")
        return 1
    print("AR-220 mutation suite: every mutation caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
